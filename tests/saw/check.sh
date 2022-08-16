#!/bin/bash

# code formatting
black *.py

# code checking
mypy *.py
flake8 *.py
