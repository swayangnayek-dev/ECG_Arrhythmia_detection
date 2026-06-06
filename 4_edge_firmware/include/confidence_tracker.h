#pragma once
#include "config.h"

class ConfidenceTracker {
public:
    ConfidenceTracker(float threshold, int required_count)
        : threshold_(threshold), required_(required_count),
          count_(0), last_class_(-1) {}

    /**
     * @brief Update tracker with new prediction.
     * @return true if alert should be triggered.
     *
     * Logic: If the SAME irregular class is predicted with confidence
     *        > threshold for `required_` consecutive windows -> trigger.
     *        A class change or low confidence resets the counter.
     */
    bool update(int predicted_class, float confidence) {
        if (confidence >= threshold_ && predicted_class == last_class_) {
            count_++;
        } else if (confidence >= threshold_) {
            // New irregular class - restart counting
            last_class_ = predicted_class;
            count_ = 1;
        } else {
            reset();
        }
        return (count_ >= required_);
    }

    void reset() {
        count_ = 0;
        last_class_ = -1;
    }

private:
    float threshold_;
    int   required_;
    int   count_;
    int   last_class_;
};
