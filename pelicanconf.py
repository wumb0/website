#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals
import re

def rmhtmltags(s):
    return re.sub('<[^>]*>', '', s)

DELHTML = rmhtmltags

AUTHOR = u'wumb0'
SITENAME = u'wumb0in\''
HEADER_SITENAME = u'wumb0.in(g)'
SITEURL = u'https://wumb0.in'

PATH = 'content'

TIMEZONE = 'America/New_York'

DEFAULT_LANG = u'en'

# Feed generation is usually not desired when developing
FEED_DOMAIN = SITEURL
FEED_ALL_ATOM = u'feeds/all.atom.xml'
CATEGORY_FEED_ATOM = 'feeds/{slug}.atom.xml'
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None
FEED_ALL_RSS = u'feeds/all.rss.xml'
CATEGORY_FEED_RSS = 'feeds/{slug}.rss.xml'

# Blogroll
LINKS = (('Pelican', 'http://getpelican.com/'),
         ('Python.org', 'http://python.org/'),
         ('Jinja2', 'http://jinja.pocoo.org/'),
         ('You can modify those links in your config file', '#'),)

# Social widget
SOCIAL = (('You can add links in your config file', '#'),
          ('Another social link', '#'),)

DEFAULT_PAGINATION = 10

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

#--------------User Conf----------------
PLUGIN_PATHS = ['pelican-plugins']
CSS_FILES = (
                "https://cdnjs.cloudflare.com/ajax/libs/uikit/2.27.5/css/uikit.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/uikit/2.27.5/css/uikit.gradient.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/uikit/2.27.5/css/components/tooltip.gradient.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.1.2/styles/default.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.6.3/css/font-awesome.min.css",
                "/theme/custom.css",
            )
JS_FILES = (
                "https://code.jquery.com/jquery-2.2.4.min.js",
                "https://cdnjs.cloudflare.com/ajax/libs/uikit/2.27.5/js/uikit.min.js",
                "https://cdnjs.cloudflare.com/ajax/libs/uikit/2.27.5/js/components/tooltip.min.js",
                "https://cdnjs.cloudflare.com/ajax/libs/uikit/2.27.5/js/core/dropdown.min.js",
                "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.1.2/highlight.min.js",
                "/theme/custom.js",
           )
THEME = 'themes/mytheme1'
FAVICON = 'favicon.ico'
PLUGINS = [ 'pelican_fontawesome', 'minification',]# 'better_figures_and_images' ]
RESPONSIVE_IMAGES = True
DISPLAY_CATEGORIES_ON_MENU = True
DISPLAY_PAGES_ON_MENU = True
PAGINATION_PATTERNS = (
    (1, '{base_name}/', '{base_name}/index.html'),
    (2, '{base_name}/page/{number}/', '{base_name}/page/{number}/index.html'),
)
TAG_URL = 'tag/{slug}/'
TAG_SAVE_AS = 'tag/{slug}/index.html'
TAGS_URL = 'tags/'
TAGS_SAVE_AS = 'tags/index.html'

AUTHOR_URL = 'author/{slug}/'
AUTHOR_SAVE_AS = 'author/{slug}/index.html'
AUTHORS_URL = 'authors/'
AUTHORS_SAVE_AS = 'authors/index.html'

CATEGORY_URL = 'category/{slug}/'
CATEGORY_SAVE_AS = 'category/{slug}/index.html'
CATEGORYS_URL = 'categories/'
CATEGORYS_SAVE_AS = 'categories/index.html'
PAGE_ORDER_BY = 'sortorder'
STATIC_PATHS = ['files', 'images']
MARKDOWN = {
    'extension_configs': {
        'markdown.extensions.codehilite': {'css_class': 'highlight'},
        'markdown.extensions.extra': {},
        'markdown.extensions.meta': {},
    },
    'output_format': 'html5',
}

import sys, os
sys.path.append(os.path.dirname(__file__))
import postfilter
JINJA_FILTERS = {'datefilter':postfilter.datefilter}
#--------------/User Conf----------------
