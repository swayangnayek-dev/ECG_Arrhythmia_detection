cmake_minimum_required(VERSION 3.10)
project(ECG_Arrhythmia_detection_Firmware)

set(CMAKE_CXX_STANDARD 14)

include_directories(include)

add_executable(firmware
    src/main.cpp
)

# Note: Requires STM32Cube toolchain and TFLite Micro libraries
# to be linked for an actual MCU build.
