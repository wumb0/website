Title: Simple Limited Backup Script
Date: 2014-05-25 00:53
Category: Old Posts
Tags: old
Slug: Simple-Limited-Backup-Script
Authors: wumb0

I was setting up cron tasks for updating and backing up this site today and wrote a very simple script to backup mysql and keep only the 10 most recent backups. Check it out:

```bash
#!/bin/bash
date=<code>date +%m%d%Y-%H%M%S</code>
cd $@
mysqldump --user=backupuser --password="mysqluserpassword" --all-databases --add-drop-table 2>/dev/null > mysql-backup-$date.sql

ls -t \| tail -n +11 \| xargs rm &>/dev/null
```
This script dumps all databases and saves it as mysql-backup-<strong>$date</strong>.sql where <strong>$date</strong> is "MonthDayFullyear-HourMinSec" in a directory passed as an argument.
Then it does an <strong>ls -t</strong> on the directory the backups are stored in (<strong>-t</strong> sorts ascending by date) then <strong>tail</strong>-ing lines 11 and up, ignoring the first 10. This is then fed to <strong>xargs rm</strong> to remove all but the 10 newest backups. I thought it was neat because it doesn't even require an if statement but still gets the job done. Obviously this can be used for other types of backups, too; just use the last line of this script after backing things up and you are good to go!

(the user <em>backupuser</em> only has read permissions on the DBs, so putting the password in this script isn't such a big deal)
