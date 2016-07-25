Title: Compiling Redistributable DLL Independent in Visual Studio
Date: 2014-06-06 13:07
Category: Old Posts
Tags: old
Slug: Compiling-Redistributable-DLL-Independent-in-Visual-Studio
Authors: wumb0

I just was looking into this today and figured it was worth posting about. Usually code compiled with Visual Studio needs a redistributable package (ex. C++ Redistributables) to run. This is a set of DLLs that allows resulting executable to be smaller by having common function calls be distributed in the DLL rather than in the executable file itself. There is a way to turn this off though so your malware/program/whatever can stand on its own.

<div class="uk-thumbnail"><a href="/images/old/uploads/2014/06/Screen-Shot-2014-06-06-at-2.02.30-PM.png"><img class="uk-align-center" src="/images/old/uploads/2014/06/Screen-Shot-2014-06-06-at-2.02.30-PM.png" alt="Build-Properties" width="779" height="338" /></a>
<div class="uk-thumbnail-caption"><strong>Project -&gt; [Project Name] -&gt; Properties</strong></div>
</div>


<div class="uk-thumbnail"><a href="/images/old/uploads/2014/06/Screen-Shot-2014-06-06-at-2.02.50-PM.png"><img class="wp-image-291 size-full" src="/images/old/uploads/2014/06/Screen-Shot-2014-06-06-at-2.02.50-PM.png" alt="Configuration" width="874" height="447" /></a>
<div class="uk-thumbnail-caption"><strong>Configuration Properties -&gt; C/C++ (or whatever language) -&gt; Code Generation -&gt; Runtime Library -&gt; Set to Multi-Threaded (/MT)</strong></div>
</div>
It's as easy as that!
