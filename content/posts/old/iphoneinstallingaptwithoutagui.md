Title: iPhone: Installing apt without a gui
Date: 2015-12-01 15:49
Category: Old Posts
Tags: old
Slug: iPhone:-Installing-apt-without-a-gui
Authors: wumb0

Usually to get apt you need to launch Cydia. If you only have an ssh connection in and would like apt you can go to <a href="http://apt.saurik.com/debs/" target="_blank">http://apt.saurik.com/debs/</a> and grab berkeleydb_4.6.21-5_iphoneos-arm.deb and apt7_0.7.25.3-8_iphoneos-arm.deb. Scp them over and run dpkg -i apt7_0.7.25.3-8_iphoneos-arm.deb then dpkg -i berkeleydb_4.6.21-5_iphoneos-arm.deb. There you go. You can apt-get all of the things now.
