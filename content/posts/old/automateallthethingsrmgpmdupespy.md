Title: Automate ALL THE THINGS - rmGPMdupes.py
Date: 2014-03-23 19:22
Category: Old Posts
Tags: old
Slug: Automate-ALL-THE-THINGS---rmGPMdupes.py
Authors: wumb0

I recently decided to switch from Spotify Premium to Google Play Music Unlimited for a couple of reasons. The main one being the mobile app that each has to offer. A couple of months ago I decided that I wanted to pay for a music service because it would end up costing the equivalent of one album per month, which is way less than I actually bought. I wanted a service that had a big catalog, a good mobile app, and the ability to sync my local songs that were not in the service's database. The obvious first reaction choice was Spotify because I had been using it for free for a while and had actually paid for and used the Premium version on my iPhone previously. There was, on the other hand, Google Play Music Unlimited, which was made known to me via the Google Play Music app on my Galaxy S4 that I got in July. I had already known of Google Play music and had already uploaded around 10,000 of my songs to it, but had just recently seen the Unlimited service. The main turn off about Google Play Music unlimited at the time was the app. It did not allow you to store your downloaded tracks locally on the external SD card, only the internal one. The Spotify app did. So that's what I went with...

The Spotify app developed some problems over the time that I paid for the service. One of the major let downs was the need to sync local files from my computer, which wouldn't have been so much of a problem if the app didn't delete my local songs about once a week. The sync feature would not work on the RIT wifi so I had to sync it by other means (namely setting up a shared wireless connection from my laptop and having my phone join it to sync.) Another issue I had was the noise... Music would often glitch and skip while I was listening to it. This drives me NUTS.

About a week and a half ago I took another look at the Google Play Music app and to my surprise, found an option to store downloaded music on the external card. I immediately cancelled my Spotify Premium subscription and signed up for Google Play Music Unlimited.

So now the daunting task of moving my playlists over...

When I moved from iTunes to Spotify I used an online converter to import my playlists, and have made some since. Google Play Music Manager automatically updates playlists from iTunes as they are made. The problem with this is that these playlists sometimes (most of the time) contain duplicate songs. This is annoying as I like my playlists nice and organized with no duplicates.

So I found myself going through and deleting all of the duplicates manually for about 5 playlists... and then I said to myself. "there has to be a way to automate this."

Sure enough, Googling "google play music api" resulted in the <a title="Link to the API" href="http://unofficial-google-music-api.readthedocs.org/" target="_blank">Unofficial Google Music API</a> by Simon Weber written in python.

I am sort of new to python at this point but I am actively learning it by taking on small projects such as this. I am also reading the "Violent Python" and "Grey Hat Python" books to help me apply the language to my profession.

So here it is... rmGPMdupes.py: <a href="https://github.com/jgeigerm/rmGPMdupes" target="_blank">https://github.com/jgeigerm/rmGPMdupes</a>

It took about 4 hours to get to know the API and fix bugs but it works and I can use my Google Play Music player without going crazy due to the duplicate songs in my playlists!

Now back to moving playlists from Spotify to Play Music... *grumble*
