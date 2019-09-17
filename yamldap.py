#!/usr/bin/python
import argparse
import os
import oyaml as yaml
import json
import jinja2
from getpass import getpass
from collections import OrderedDict

import signal
import sys
signal.signal(signal.SIGINT, lambda x, y: sys.exit(128 + signal.SIGINT))

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# First get a list of schemas
schema_names = []

for root, dirs, files in os.walk('./schema/'):
  for filename in files:
    if (filename.endswith('.yml')):
      schema_names.append(filename.replace('.yml',''))

parser = argparse.ArgumentParser(description='yamldap - ldap utils using yaml')
parser.add_argument('-m', '--may', action='store_true', default=False, help='prompt for optional attributes')
parser.add_argument('-v', '--verbose', action='store_true', help='print extra information')
parser.add_argument('-l', '--ldif', action='store_true', help='don\'t apply changes, just create ldif')
parser.add_argument('-f', '--file', help='where to save file')
parser.add_argument('-r', '--repo', help='name of repository for settings')

subparsers = parser.add_subparsers(title='Actions', help='The action to perform')
subp_add = subparsers.add_parser('add', help='add an entry')
subp_add.add_argument('schema', choices=schema_names)
subp_add.add_argument('identifier', help='primary key for entry')
subp_add.set_defaults(which='add')

subp_modify = subparsers.add_parser('modify', help='modify an entry')
subp_modify.add_argument('schema', help='type of entry')
subp_modify.add_argument('key', help='primary key e.g \'tom.fiddle\' if uid=tom.fiddle')
subp_modify.set_defaults(which='modify')

subp_convert = subparsers.add_parser('ldif2yaml', help='convert ldif to yaml')
subp_convert.add_argument('src', help='source ldif file')
subp_convert.add_argument('dst', help='dest ldif file')
subp_convert.set_defaults(which='ldif2yaml')

modify_parser = subp_modify.add_subparsers(title='Actions', help='the action to peform')
act_replace = modify_parser.add_parser('replace')
act_replace.add_argument('attribute', help='attribute to replace')
act_replace.add_argument('value', help='value to set', nargs='?')
act_replace.set_defaults(modify_type='replace')

act_add = modify_parser.add_parser('add')
act_add.add_argument('attribute', help='attribute to add')
act_add.add_argument('value', help='value to add', nargs='?')
act_add.set_defaults(modify_type='add')

act_del = modify_parser.add_parser('delete')
act_del.add_argument('attribute', help='attribute to delete')
act_del.add_argument('value', default='', nargs='?', help='optional value')
act_del.set_defaults(modify_type='delete')

act_inc = modify_parser.add_parser('increment')
act_inc.add_argument('attribute', help='attribute to increment')
act_inc.set_defaults(modify_type='increment')


args = parser.parse_args()

schemas = OrderedDict()

def first(s):
    '''Return the first element from an ordered collection
       or an arbitrary element from an unordered collection.
       Raise StopIteration if the collection is empty.
    '''
    return next(iter(s))

def LoadSchema(name):
  with open('./schema/'+name+'.yml', 'r') as f:
    content = f.read()
    content = yaml.load(content)
    content['attributes'] = content.get('required')
    content['attributes'] += content.get('optional')
    content['_attr_secret'] = []
    content['_attr_sensative'] = []

    for attr in content.get('attributes'):
      if (attr.get('secret')):
        content['_attr_secret'].append(attr.get('name'))
      if (attr.get('sensative')):
        content['_attr_sensative'].append(attr.get('name'))

    if args.verbose:
      print(bcolors.WARNING + 'Loaded Schema: ' + json.dumps(content) + bcolors.ENDC)

    return content

def LoadDefaults(schema):
  with open('./etc/defaults.yml', 'r') as f:
    content = f.read()
    data = yaml.load(content)

    warn = False
    if args.repo:
      if 'repositories' in data:
        if args.repo in data.get('repositories'):
          data.update(data.get('repositories').get(args.repo))
        else:
          warn = True
      else:
        warn = True

    if warn:   
      print("WARNING: Unable to find repository " + args.repo + " in defaults")
      print("         Some attributes may have the wrong values. Please check your spelling")
    
    defaults = OrderedDict()

    for item in schema.get('required'):
      attr_name = item.get('name')
      if attr_name in data:
        defaults[attr_name] = data.get(attr_name)
    for item in schema.get('optional'):
      attr_name = item.get('name')
      if attr_name in data:
        defaults[attr_name] = data.get(attr_name)
    return defaults

def GetAnswers(answers, attributes, defaults, required):
  for item in attributes:
    val = ''
    needs_answer = True
    attr_name = item.get('name')
    while (needs_answer):
      if attr_name in defaults:
        template = jinja2.Template(defaults.get(attr_name))
        val = template.render(answers)
      if (item.get('secret')):
        val = getpass('{secret} ' + attr_name + ': ')
      else:
        val = raw_input(attr_name + ' ['+val+']: ') or val

      if val != '' or not required:
          needs_answer = False
      elif required:
        print('\n' + attr_name + ' is a required attribute. Please provide input')
      answers[attr_name] = val
  return answers

def SaveLDIF(lines):
  filename = ''
  if args.file:
    filename = args.file
  else:
    lines.append('')
    print('\n'.join(lines))
    return None

  with open(filename, 'w') as f:
    for item in lines:
        f.write("%s\n" % item)

  print('Writing ldif to \'' + filename +'\'')
  return filename

def GetBaseFromSchema(schema):
  return settings.get(schema.get('type') + '_base')

def GenerateDN(schema, value, base):
  return (first(schema.get('required')).get('name') + '=' + value + ',' + base)

def CreateAddLDIF(schema, values):
  # Same as everywhere else, the first value is the primary key for the distinguished name
  # Schema type decides what base gets pulled from settings, if type is "user" then the setting will be user_base
  # likewise for group, group_base
  lines = []
  base = GetBaseFromSchema(schema)
  lines.append('dn: ' + GenerateDN(schema, values.get(first(values)), base))
  for objectclass in schema.get('objectclasses'):
    lines.append('objectclass: ' + objectclass)
  for item in values.iteritems():
    if item[1]:
      lines.append(item[0] + ': ' + item[1])

  return SaveLDIF(lines)

# First things first, load all of the settings
settings = {}
with open('./etc/settings.yml', 'r') as f:
  settings = yaml.load(f.read())

  warn = False
  if args.repo:
    if 'repositories' in settings:
      if args.repo in settings.get('repositories'):
        settings.update(settings.get('repositories').get(args.repo))
      else:
        warn = True
    else:
      warn = True

  if warn:
    print("WARNING: Unable to find repository " + args.repo + " in settings")
    print("         Some attributes may have the wrong values. Please check your spelling")




def CreateModifyLDIF(schema, items, operation):
  lines = []
  base = GetBaseFromSchema(schema)
  lines.append('dn: ' + GenerateDN(schema, args.key, base))
  lines.append('changetype: modify')
  for item in items:
    lines.append(operation + ': ' + item)
    if (items[item] != ''):
      lines.append(item + ': ' + items[item])
    lines.append('-')
  del lines[-1]
  SaveLDIF(lines)

if (args.which == 'add'):
  print("Adding " + args.schema + " entry " + args.identifier)
  
  schema = LoadSchema(args.schema)
  defaults = LoadDefaults(schema)
  if args.verbose:
    print(bcolor.WARNING + 'Default values: ' + json.dumps(defaults) + bcolor.ENDC)
  answers = OrderedDict()

  # The first attribute specified in schema will be considerd the primary key
  answers[schema.get('required').pop(0).get('name')] = args.identifier
  answers.update(defaults)
  answers = GetAnswers(answers, schema.get('required'), defaults, True)

  if args.may:
    answers = GetAnswers(answers, schema.get('optional'), defaults, False)
  else:
    for item in schema.get('optional'):
      attr_name = item.get('name')
      if attr_name in defaults:
        template = jinja2.Template(defaults.get(attr_name))
        val = template.render(answers)
        answers[attr_name] = val

  print(answers)
  file = CreateAddLDIF(schema, answers)

if args.which == 'modify':
  schema = LoadSchema(args.schema)

  value = args.value

  if value == None:
    if args.attribute in schema.get('_attr_secret'):
      value = getpass(bcolors.BOLD + '{secret} '+ bcolors.ENDC + args.attribute + ': ')
    if args.attribute in schema.get('_attr_sensative'):
      value = raw_input(args.attribute + ': ')
  else:
    if ((args.attribute in schema.get('_attr_secret')) or (args.attribute in schema.get('_attr_sensative'))):
      print(bcolors.FAIL + "Oops! Looks like you specified a sensative value on the shell." + bcolors.ENDC)
      print(bcolors.FAIL + "      You might want to remove that command from the shell's history." + bcolors.ENDC)

  items = {}
  items[args.attribute] = value
  CreateModifyLDIF(schema, items, args.modify_type)  

if args.which == 'ldif2yaml':
  with open(args.src, 'r') as source:
    with open(args.dst, 'w') as dest:
      line = source.readline()
      entries = 0
      data = ''
      total_read = 0
      src_size = os.stat(args.src).st_size
      while line:
        if line.isspace():
          dest.write('- ' + yaml.dump(yaml.load(data)).strip() + '\n')
          total_read += len(data)
          entries += 1
          data = ''
          sys.stdout.write('\r%d%% Bytes read %d MB (Processed %d entries)' % ((total_read / src_size), total_read / 1024 / 1024, entries) )
        else:
          data += line
        line = source.readline()
