YamLDAP
================================================

An LDIF generator using YAML for configuration and Jinja2 for templating. 

## Features
- Generate Add LDIF
- Generate Modify LDIF
  - Replace
  - Add
  - Delete
  - Increment

- Ability to make attributes secret or sensative to keep them out of shell history
- Ability to set defaults, and use Jinja2 templates in them

## Getting Started

First things first, create a schema file. Remember that the first required attribute (or may attribute if no required attributes exist) is considered the primary key. The requires block must at a **minimum** have all attributes that are required by the objectclasses specified, however may attributes can be specified as required e.g. loginShell.

```yaml
name: PosixAccount
type: user
objectclasses: ['posixAccount', 'top']
requires:
  - { name: uid, sensative: true }
  - { name: cn }
  - { name: uidnumber }
  - { name: gidnumber }
  - { name: homeDirectory }
may:
  - { name: loginShell }
  - { name: gecos }
  - { name: description }
  - { name: authPassword, secret: true }
private_attrs:
  - authPassword
```

### Add an entry
```
usage: yamldap.py add [-h] {PosixAccount,LinuxUser} identifier

positional arguments:
  PosixAccount
  identifier            primary key for entry

optional arguments:
  -h, --help            show this help message and exit
```

Below is how you would add an entry skipping the optional attributes. If you would like to be prompted for optional attributes then use the -m flag like
`./yamldap -m add ...`

```bash
$ ./yamldap.py add PosixAccount someuser
Adding PosixAccount entry someuser
cn [someuser]: 
uidnumber []: 10000
gidnumber []: 10000
homeDirectory [/nfs/home/someuser]
```

The ldif generated
```
dn: uid=someuser,ou=users,dc=example
objectclass: posixAccount
objectclass: top
uid: someuser
cn: someuser
homeDirectory: /nfs/home/someuser
loginShell: /bin/bash
gecos: someuser
uidnumber: 10000
gidnumber: 10000
```