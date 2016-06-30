#!/bin/bash
pelican/bin/pelican content -s pelicanconf.py -t "themes/$1"
