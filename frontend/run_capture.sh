#!/bin/bash
echo "Starting capture wrapper..." > capture_wrapper.log
node scripts/capture.js >> capture_wrapper.log 2>&1
echo "Exit code: $?" >> capture_wrapper.log
