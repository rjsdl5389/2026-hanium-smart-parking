#include "actuator.h"

#include <math.h>

#include "app_config.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/* Local app_config.h is gitignored; keep old local configs buildable. */
#ifndef PWM_STRONG_TURN_MIN
#define PWM_STRONG_TURN_MIN PWM_TURN_MIN
#endif

#if ENABLE_ACTUATOR_OUTPUT
#include "driver/gpio.h"
#include "driver/ledc.h"
#endif

static const char *TAG = "ACTUATOR";

#if ENABLE_ACTUATOR_OUTPUT
#define MOTOR_LEDC_TIMER   LEDC_TIMER_0
#define MOTOR_LEDC_CHANNEL LEDC_CHANNEL_0
#define SERVO_LEDC_TIMER   LEDC_TIMER_1
#define SERVO_LEDC_CHANNEL LEDC_CHANNEL_1
#define LEDC_MODE          LEDC_LOW_SPEED_MODE
#endif

static double s_last_servo_angle_deg = SERVO_CENTER_DEG;

static double clampd(double value, double lo, double hi)
{
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

static double lerpd(double a, double b, double t)
{
    return a + (b - a) * clampd(t, 0.0, 1.0);
}

/*
 * Piecewise steering calibration from the 2026-07-29 bench test:
 *   -1.0 -> 30°, -0.5 -> 60°, 0 -> 86°, +0.5 -> 112°, +1.0 -> 122°.
 */
static double steering_to_angle(double steering)
{
    const double s = clampd(steering, -1.0, 1.0);
    if (s <= -0.5) {
        return lerpd(SERVO_LEFT_STRONG_DEG, SERVO_LEFT_WEAK_DEG, (s + 1.0) / 0.5);
    }
    if (s < 0.0) {
        return lerpd(SERVO_LEFT_WEAK_DEG, SERVO_CENTER_DEG, (s + 0.5) / 0.5);
    }
    if (s <= 0.5) {
        return lerpd(SERVO_CENTER_DEG, SERVO_RIGHT_WEAK_DEG, s / 0.5);
    }
    return lerpd(SERVO_RIGHT_WEAK_DEG, SERVO_RIGHT_STRONG_DEG, (s - 0.5) / 0.5);
}

/*
 * Steering-dependent motor profile (latest real-car calibration):
 *   straight: min 12, default 22
 *   weak turn (|steering|=0.5): min 32, default 40
 *   strong turn (|steering|=1.0): min 32, default 50
 *
 * 이전 구현은 |steering|=1.0에서 min==default==strong default가 되어 host
 * throttle이 완전히 무시됐다. 아래 mapping은 강조향에서도 최소 토크 floor와
 * throttle-controlled range를 분리해 저속 정밀주차/후진 recovery를 가능하게 한다.
 */
static int throttle_to_duty(double throttle, double steering)
{
    const double magnitude = fabs(clampd(throttle, -1.0, 1.0));
    if (magnitude <= MOTOR_DEADBAND_THROTTLE) return 0;

    const double abs_steering = fabs(clampd(steering, -1.0, 1.0));
    double min_duty;
    double default_duty;

    if (abs_steering <= 0.5) {
        const double t = abs_steering / 0.5;
        min_duty = lerpd(PWM_FORWARD_MIN, PWM_TURN_MIN, t);
        default_duty = lerpd(PWM_FORWARD_DEFAULT, PWM_TURN_DEFAULT, t);
    } else {
        const double t = (abs_steering - 0.5) / 0.5;
        min_duty = lerpd(PWM_TURN_MIN, PWM_STRONG_TURN_MIN, t);
        default_duty = lerpd(PWM_TURN_DEFAULT, PWM_STRONG_TURN_DEFAULT, t);
    }

    int duty = (int)lround(lerpd(min_duty, default_duty, magnitude));
    if (duty < 0) duty = 0;
    if (duty > MOTOR_PWM_MAX_DUTY) duty = MOTOR_PWM_MAX_DUTY;
    return duty;
}

#if ENABLE_ACTUATOR_OUTPUT
static uint32_t servo_angle_to_duty(double angle_deg)
{
    const double angle = clampd(angle_deg, 0.0, SERVO_FULL_SWEEP_DEG);
    const double pulse_us = SERVO_MIN_PULSE_US +
        (angle / SERVO_FULL_SWEEP_DEG) * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US);
    const double period_us = 1000000.0 / (double)SERVO_PWM_FREQ_HZ;
    const double max_count = (double)((1u << SERVO_PWM_RES_BITS) - 1u);
    const double duty = clampd((pulse_us / period_us) * max_count, 0.0, max_count);
    return (uint32_t)lround(duty);
}

static void motor_write(int duty, motion_direction_t direction)
{
    const int direction_level = (direction == MOTION_DIRECTION_REVERSE)
        ? MOTOR_REVERSE_DIR_LEVEL : MOTOR_FORWARD_DIR_LEVEL;
    gpio_set_level(MOTOR_DIR_GPIO, direction_level);
    ledc_set_duty(LEDC_MODE, MOTOR_LEDC_CHANNEL, (uint32_t)duty);
    ledc_update_duty(LEDC_MODE, MOTOR_LEDC_CHANNEL);
}

static void servo_write(double angle_deg)
{
    ledc_set_duty(LEDC_MODE, SERVO_LEDC_CHANNEL, servo_angle_to_duty(angle_deg));
    ledc_update_duty(LEDC_MODE, SERVO_LEDC_CHANNEL);
    s_last_servo_angle_deg = angle_deg;
}

static void initialize_servo_first(void)
{
    ledc_timer_config_t servo_timer = {
        .speed_mode = LEDC_MODE,
        .duty_resolution = LEDC_TIMER_14_BIT,
        .timer_num = SERVO_LEDC_TIMER,
        .freq_hz = SERVO_PWM_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&servo_timer));

    ledc_channel_config_t servo_channel = {
        .gpio_num = SERVO_PWM_GPIO,
        .speed_mode = LEDC_MODE,
        .channel = SERVO_LEDC_CHANNEL,
        .timer_sel = SERVO_LEDC_TIMER,
        .duty = 0,
        .hpoint = 0,
        .intr_type = LEDC_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&servo_channel));

    servo_write(SERVO_CENTER_DEG);
    vTaskDelay(pdMS_TO_TICKS(SERVO_BOOT_CENTER_DELAY_MS));
}

static void initialize_motor_after_servo(void)
{
    gpio_config_t direction_config = {
        .pin_bit_mask = (1ULL << MOTOR_DIR_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&direction_config));

    ledc_timer_config_t motor_timer = {
        .speed_mode = LEDC_MODE,
        .duty_resolution = LEDC_TIMER_8_BIT,
        .timer_num = MOTOR_LEDC_TIMER,
        .freq_hz = MOTOR_PWM_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&motor_timer));

    ledc_channel_config_t motor_channel = {
        .gpio_num = MOTOR_PWM_GPIO,
        .speed_mode = LEDC_MODE,
        .channel = MOTOR_LEDC_CHANNEL,
        .timer_sel = MOTOR_LEDC_TIMER,
        .duty = 0,
        .hpoint = 0,
        .intr_type = LEDC_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&motor_channel));

    ESP_ERROR_CHECK(gpio_set_pull_mode(MOTOR_PWM_GPIO, GPIO_PULLDOWN_ONLY));
    ESP_ERROR_CHECK(gpio_set_pull_mode(MOTOR_DIR_GPIO, GPIO_PULLDOWN_ONLY));
    motor_write(0, MOTION_DIRECTION_FORWARD);
}
#endif

void actuator_init(void)
{
#if ENABLE_ACTUATOR_OUTPUT
    /* Verified safe order: attach/center servo first, then configure motor PWM. */
    initialize_servo_first();
    initialize_motor_after_servo();
    ESP_LOGW(TAG,
             "Real actuator output ENABLED: motor PWM GPIO%d (8-bit), DIR GPIO%d, servo GPIO%d",
             MOTOR_PWM_GPIO, MOTOR_DIR_GPIO, SERVO_PWM_GPIO);
#else
    s_last_servo_angle_deg = SERVO_CENTER_DEG;
    ESP_LOGW(TAG,
             "Mock actuator initialized: PWM 8-bit calibration, servo center %.1f deg, no GPIO output",
             SERVO_CENTER_DEG);
#endif
}

void actuator_safe_stop(const char *reason)
{
    (void)reason;
#if ENABLE_ACTUATOR_OUTPUT
    motor_write(0, MOTION_DIRECTION_FORWARD);
    servo_write(SERVO_CENTER_DEG);
    ESP_LOGW(TAG, "safeStop(reason=%s): motor=0 servo=center",
             reason ? reason : "UNKNOWN");
#else
    s_last_servo_angle_deg = SERVO_CENTER_DEG;
    ESP_LOGW(TAG, "safeStop(reason=%s): mock motor=0 servo=%.1f",
             reason ? reason : "UNKNOWN", SERVO_CENTER_DEG);
#endif
}

void actuator_start_motion(void)
{
    ESP_LOGI(TAG, "MOVING (WAYPOINT_AUTO); direct output governed by control task");
}

void actuator_apply_direct(double throttle, double steering, actuator_output_t *out)
{
    double effective_throttle = clampd(throttle, -1.0, 1.0);
    const double effective_steering = clampd(steering, -1.0, 1.0);

    motion_direction_t direction = MOTION_DIRECTION_FORWARD;
    if (effective_throttle < 0.0) {
        direction = MOTION_DIRECTION_REVERSE;
#if !MOTOR_ALLOW_REVERSE
        effective_throttle = 0.0;
        direction = MOTION_DIRECTION_FORWARD;
#endif
    }

    const int duty = throttle_to_duty(effective_throttle, effective_steering);
    const double angle = steering_to_angle(effective_steering);

#if ENABLE_ACTUATOR_OUTPUT
#if STOP_MOTOR_DURING_STEER_UPDATE
    if (fabs(angle - s_last_servo_angle_deg) >= 0.5) {
        motor_write(0, direction);
        servo_write(angle);
        vTaskDelay(pdMS_TO_TICKS(STEER_UPDATE_SETTLE_MS));
    }
#else
    servo_write(angle);
#endif
    motor_write(duty, direction);
#else
    s_last_servo_angle_deg = angle;
    ESP_LOGI(TAG, "mock apply thr=%.3f str=%.3f -> pwm=%d/255 dir=%s servo=%.1fdeg",
             effective_throttle, effective_steering, duty,
             motion_direction_to_string(direction), angle);
#endif

    if (out) {
        out->motor_pwm = duty;
        out->motor_direction = direction;
        out->servo_angle_deg = angle;
        out->applied_throttle = effective_throttle;
        out->applied_steering = effective_steering;
    }
}

bool actuator_output_enabled(void)
{
#if ENABLE_ACTUATOR_OUTPUT
    return true;
#else
    return false;
#endif
}
