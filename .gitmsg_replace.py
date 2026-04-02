#!/usr/bin/env python
import sys
import re

def main():
    data = sys.stdin.read()
    # Replace 'lovable' (case-insensitive) with project display name
    out = re.sub(r'(?i)lovable', 'Secure Gig Guardian', data)
    sys.stdout.write(out)

if __name__ == '__main__':
    main()
