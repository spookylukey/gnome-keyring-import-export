#!/usr/bin/env python

# Simple script for exporting gnome2 (seahorse) keyrings,
# and re-importing on another machine.

# Usage:
#
# Export:
#
#   gnome_keyring_import_export.py export somefile.json
#
#
# Please note - this dumps all your passwords *unencrypted*
# into somefile.json
#
# Import
#
#   gnome_keyring_import_export.py import somefile.json
#
# This attempts to be intelligent about not duplicating
# secrets already in the keyrings - see messages.
#
# However, if you are moving machines, sometimes an application
# name changes (e.g. "chrome-12345" -> "chrome-54321") so
# you might need to do some manual fixes on somefile.json first.
#
# Please make BACKUP copies of your existing keyring files
# before importing into them, in case anything goes wrong.
# They are normally found in:
#
#  ~/.gnome2/keyrings 
#  ~/.local/share/keyrings



import json
import sys

import pygtk
pygtk.require('2.0')
import gtk # sets app name
import gnomekeyring

def mk_copy(item):
    c = item.copy()
    c['attributes'] = c['attributes'].copy()
    return c

def remove_insignificant_data(item, ignore_secret=False):
    item.pop('mtime', None)
    item.pop('ctime', None)
    item.pop('mtime', None)
    item['attributes'].pop('date_created', None)
    if ignore_secret:
        item.pop('secret', None)

def items_roughly_equal(item1, item2, ignore_secret=False):
    c1 = mk_copy(item1)
    c2 = mk_copy(item2)

    remove_insignificant_data(c1, ignore_secret=ignore_secret)
    remove_insignificant_data(c2, ignore_secret=ignore_secret)

    return c1 == c2

def export_keyrings(to_file):
    file(to_file, "w").write(json.dumps(get_gnome_keyrings(), indent=2))

def get_gnome_keyrings():
    keyrings = {}
    for keyring_name in gnomekeyring.list_keyring_names_sync():
        keyring_items = []
        keyrings[keyring_name] = keyring_items
        for id in gnomekeyring.list_item_ids_sync(keyring_name):
            item = get_item(keyring_name, id)
            if item is not None:
                keyring_items.append(item)

    return keyrings

def get_item(keyring_name, id):
    try:
        item = gnomekeyring.item_get_info_sync(keyring_name, id)
    except gnomekeyring.IOError as e:
        sys.stderr.write("Could not examine item (%s, %s): %s\n" % (keyring_name, id, e.message))
        return None
    return {
        'display_name': item.get_display_name(),
        'secret': item.get_secret(),
        'mtime': item.get_mtime(),
        'ctime': item.get_ctime(),
        'attributes': gnomekeyring.item_get_attributes_sync(keyring_name, id),
        }


def fix_attributes(d):
    return {str(k): str(v) if isinstance(v, unicode) else v for k, v in d.items()}


def import_keyrings(from_file):
    keyrings = json.loads(file(from_file).read())

    for keyring_name, keyring_items in keyrings.items():
        try:
            existing_ids = gnomekeyring.list_item_ids_sync(keyring_name)
        except gnomekeyring.NoSuchKeyringError:
            sys.stderr.write("No keyring '%s' found. Please create this keyring first" % keyring_name)
            sys.exit(1)

        existing_items = [get_item(keyring_name, id) for id in existing_ids]
        existing_items = [i for i in existing_items if i is not None]

        for item in keyring_items:
            if any(items_roughly_equal(item, i) for i in existing_items):
                print "Skipping %s because it already exists" % item['display_name']
            else:
                nearly = [i for i in existing_items if items_roughly_equal(i, item, ignore_secret=True)]
                if nearly:
                    print "Existing secrets found for '%s'" % item['display_name']
                    for i in nearly:
                        print " " + i['secret']

                    print "So skipping value from '%s':" % from_file
                    print " " + item['secret']
                else:
                    schema = item['attributes']['xdg:schema']
                    item_type = None
                    if schema ==  u'org.freedesktop.Secret.Generic':
                        item_type = gnomekeyring.ITEM_GENERIC_SECRET
                    elif schema == u'org.gnome.keyring.Note':
                        item_type = gnomekeyring.ITEM_NOTE
                    elif schema == u'org.gnome.keyring.NetworkPassword':
                        item_type == gnomekeyring.ITEM_NETWORK_PASSWORD

                    if item_type is not None:
                        item_id = gnomekeyring.item_create_sync(keyring_name,
                                                                item_type,
                                                                item['display_name'],
                                                                fix_attributes(item['attributes']),
                                                                item['secret'],
                                                                False)
                        print "Copying secret %s" % item['display_name']
                    else:
                        print "Can't handle secret '%s' of type '%s', skipping" % (item['display_name'], schema)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        if sys.argv[1] == "export":
            export_keyrings(sys.argv[2])
        if sys.argv[1] == "import":
            import_keyrings(sys.argv[2])
