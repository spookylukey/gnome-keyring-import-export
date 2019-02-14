#!/usr/bin/env python3

# Simple script for exporting gnome2 (seahorse) keyrings,
# using the SecretService API.

# Requirements:
#
# Python 3.5+
#
# secretstorage module. You can install this with:
#
#  pip install secretstorage

# Usage:
#
# 1) Export:
#
#   python secret_service_export.py export somefile.json
#
# Please note - this dumps all your passwords *unencrypted*
# into somefile.json
#
# 2) Import:
#
#    Not yet implemented.

import json
import sys
import urllib

import secretstorage


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
    open(to_file, "w").write(json.dumps(get_gnome_keyrings(), indent=2))


def get_gnome_keyrings():
    connection = secretstorage.dbus_init()
    keyrings = {}
    for collection in secretstorage.get_all_collections(connection):
        keyring_name = collection.collection_path
        keyrings[keyring_name] = [get_item_info(i) for i in list(collection.get_all_items())]

    return keyrings


def export_chrome_to_firefox(to_file):
    """
    Finds Google Chrome passwords and exports them to an XML file that can be
    imported by the Firefox extension "Password Exporter"
    """
    keyrings = get_gnome_keyrings()
    items = []
    item_set = set()
    for keyring_name, keyring_items in keyrings.items():
        for item in keyring_items:
            attribs = item.get_attrbutes()
            if (not item['display_name'].startswith('http') and
                    not attribs.get('application', '').startswith('chrome')):
                continue
            items.append(item)

            item_def = (attribs['signon_realm'],
                        attribs['username_value'],
                        attribs['action_url'],
                        attribs['username_element'],
                        attribs['password_element'],
                        )
            if item_def in item_set:
                sys.stderr.write("Warning: duplicate found for %r\n\n" % (item_def,))
            item_set.add(item_def)

    xml = items_to_firefox_xml(items)
    open(to_file, "w").write(xml)


def items_to_firefox_xml(items):
    import lxml.etree
    from lxml.etree import Element

    doc = Element('xml')
    entries = Element('entries',
                      dict(ext="Password Exporter", extxmlversion="1.1", type="saved", encrypt="false"))
    doc.append(entries)
    for item in items:
        attribs = item['attributes']
        url = urllib.parse.urlparse(attribs['signon_realm'])
        entries.append(Element('entry',
                               dict(host=url.scheme + "://" + url.netloc,
                                    user=attribs['username_value'],
                                    password=item['secret'],
                                    formSubmitURL=attribs['action_url'],
                                    httpRealm=url.path.lstrip('/'),
                                    userFieldName=attribs['username_element'],
                                    passFieldName=attribs['password_element'],
                                    )))
    return lxml.etree.tostring(doc, pretty_print=True)


def get_item_info(item):
    item.unlock()
    return {
        'display_name': item.get_label(),
        'secret': item.get_secret().decode('utf-8'),
        'mtime': item.get_modified(),
        'ctime': item.get_created(),
        'attributes': item.get_attributes()
        }


if __name__ == '__main__':
    if len(sys.argv) == 3:
        if sys.argv[1] == "export":
            export_keyrings(sys.argv[2])
        if sys.argv[1] == "import":
            raise NotImplementedError()
        if sys.argv[1] == "export_chrome_to_firefox":
            export_chrome_to_firefox(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "import" and not sys.stdin.isatty():
        raise NotImplementedError()

    else:
        print("See source code for usage instructions")
        sys.exit(1)
