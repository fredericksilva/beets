# This file is part of beets.
# Copyright 2013, Dang Mai <contact@dangmai.net>.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Generates smart playlists based on beets queries.
"""
from __future__ import print_function

from beets.plugins import BeetsPlugin
from beets import config, ui, library
from beets import dbcore
from beets.util import normpath, syspath
import os

# Global variable so that smartplaylist can detect database changes and run
# only once before beets exits.
database_changed = False


def query_from_parameter(lib, playlist, parameter, album=False):
    if playlist.has_key(parameter):
        # Parse quer(ies). If it's a list, join the queries with OR.
        query_strings = playlist[parameter]
        if not isinstance(query_strings, (list, tuple)):
            query_strings = [query_strings]
        model = library.Album if album else library.Item
        query = dbcore.OrQuery(
            [library.get_query(q, model) for q in query_strings]
        )
        # Execute query, depending on type
        if album:
            result = []
            for album in lib.albums(query):
                result.extend(album.items())
            return result
        else:
            return lib.items(query)
    else:
        return []


def update_playlists(lib):
    ui.print_("Updating smart playlists...")
    playlists = config['smartplaylist']['playlists'].get(list)
    playlist_dir = config['smartplaylist']['playlist_dir'].as_filename()
    relative_to = config['smartplaylist']['relative_to'].get()
    if relative_to:
        relative_to = normpath(relative_to)

    for playlist in playlists:
        items = []
        items.extend(query_from_parameter(lib, playlist, 'album_query', True))
        items.extend(query_from_parameter(lib, playlist, 'query', False))

        m3us = {}
        basename = playlist['name'].encode('utf8')
        # As we allow tags in the m3u names, we'll need to iterate through
        # the items and generate the correct m3u file names.
        for item in items:
            m3u_name = item.evaluate_template(basename, True)
            if not (m3u_name in m3us):
                m3us[m3u_name] = []
            item_path = item.path
            if relative_to:
                item_path = os.path.relpath(item.path, relative_to)
            if not item_path in m3us[m3u_name]:
                m3us[m3u_name].append(item_path)
        # Now iterate through the m3us that we need to generate
        for m3u in m3us:
            m3u_path = normpath(os.path.join(playlist_dir, m3u))
            with open(syspath(m3u_path), 'w') as f:
                for path in m3us[m3u]:
                    f.write(path + '\n')
    ui.print_("... Done")


class SmartPlaylistPlugin(BeetsPlugin):
    def __init__(self):
        super(SmartPlaylistPlugin, self).__init__()
        self.config.add({
            'relative_to': None,
            'playlist_dir': u'.',
            'playlists': []
        })

    def commands(self):
        def update(lib, opts, args):
            update_playlists(lib)
        spl_update = ui.Subcommand('splupdate',
            help='update the smart playlists')
        spl_update.func = update
        return [spl_update]


@SmartPlaylistPlugin.listen('database_change')
def handle_change(lib):
    global database_changed
    database_changed = True


@SmartPlaylistPlugin.listen('cli_exit')
def update(lib):
    if database_changed:
        update_playlists(lib)
