#!/usr/bin/python
import yaml
import sys

with open(sys.argv[1], 'r') as content:
  text = content.read()
  print(text)
  print(yaml.dump(yaml.load(text)))
