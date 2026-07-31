# Top-level ESP-IDF project file.
# NOTE: this file was ADDED in the REMOTE_DIRECT update. The original
# hanium_day3_v1 package shipped only main/ (no top-level CMakeLists), so
# `idf.py build` could not run standalone. This makes the project self-contained.
# If your existing ESP-IDF workspace already provides a top-level CMakeLists.txt,
# you may keep yours instead.
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32_main)
