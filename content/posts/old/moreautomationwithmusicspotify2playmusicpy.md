Title: More Automation With Music - spotify2playmusic.py
Date: 2014-03-26 02:25
Category: Old Posts
Tags: old
Slug: More-Automation-With-Music---spotify2playmusic.py
Authors: wumb0

I spent about 15 hours today writing another tool in python that moves Spotify playlists over to Play Music... ~300 lines later, it is done.

It is unique because it does not just do exact song matching, it does matching based on similarities in strings using the levenshtein calculation. The number returned by the levenshtein function represents how different (or not different) the two strings that were fed into the function are. A lower number means they are similar.

Anyway, here it is; it's late so I'm not going to write much more on it. All of the how-to is on my GitHub: <a href="https://github.com/jgeigerm/spotify2playmusic" target="_blank">https://github.com/jgeigerm/spotify2playmusic</a>
<p style="text-align: center;"><a href="/images/old/uploads/2014/03/Screen-Shot-2014-03-26-at-3.27.01-AM.png"><img class="size-full wp-image-85" alt="Screen Shot 2014-03-26 at 3.27.01 AM" src="/images/old/uploads/2014/03/Screen-Shot-2014-03-26-at-3.27.01-AM.png" width="1324" height="1050" /></a></p>
