#!/usr/bin/env python3
"""Rebind every time-window proof obligation to the actual test82 instance.

The shared proof generator reads this instance's rows, coefficients, intervals,
assignment supports, objective and deleted-variable set; no test81 facts enter.
"""
from prepare_test81 import main

if __name__=='__main__':main(82)
