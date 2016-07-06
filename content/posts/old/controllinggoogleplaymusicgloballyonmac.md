Title: Controlling Google Play Music Globally On Mac
Date: 2014-04-13 23:06
Category: Old Posts
Tags: old
Slug: Controlling-Google-Play-Music-Globally-On-Mac
Authors: wumb0

I spent a couple of hours today figuring out a way to control Google Play music within Chrome using the media keys on my Macbook. I'm using three different applescripts that run javascript in the Play Music page to do the desired action. Here's the base script:
<pre><code class="lang:applescript">
on run
     tell application "Google Chrome"
         set allWins to every window
         set allTabs to {}
         repeat with currWin in allWins
             set allTabs to allTabs &amp; every tab of currWin
         end repeat
         repeat with currTab in allTabs
             try
                 if (title of currTab as string) ends with "Play Music" then set musicTab to currTab
             end try
         end repeat
         tell musicTab to execute javascript "document.querySelector('[data-id=\\"play-pause\\"]').click();" -- change play-pause to forward or rewind for the other two scripts
     end tell
end run
</code></pre>
From here I used BetterTouchTool to launch the script respective to the action I wanted when the corresponding button was pressed. OSX handles media keys very strangely, though. So I am currently binding to shift-function key, with the function keys being below the media buttons. The whole key combo to play-pause ends up being fn-shift-play/pause on my keyboard. Nifty, and it doesn't even need to bring the window to the front.

Source: <a href="http://hints.macworld.com/comment.php?mode=view&amp;cid=128504" target="_blank">http://hints.macworld.com/comment.php?mode=view&amp;cid=128504</a>
