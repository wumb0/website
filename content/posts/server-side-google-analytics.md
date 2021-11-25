Title: Server Side Google Analytics
Date: 2017-09-21 19:37
Category: Sysadmin
Tags: nginx, google analytics
Slug: server-side-google-analytics
Authors: wumb0

I stitched together a bunch of posts from different sites to get a working setup for server-side google analytics with unique user tracking. This allows you to have a completely static (javascript-free) site and still get useful analytics data. 

```
server {
	# all of your other config...
        userid         on;
        userid_name    uid;
        userid_domain  <<the domain you are using this on>>;
        userid_path    /;
        userid_expires 365d;
        userid_p3p     'policyref="/w3c/p3p.xml", CP="CUR ADM OUR NOR STA NID"';

        location / {
                try_files $uri $uri/;
                index index.html;
                post_action @analytics;
        }

        location @analytics {
                internal;
                set $ipaddr $remote_addr;
                resolver 8.8.8.8 ipv6=off;
                proxy_pass https://ssl.google-analytics.com/collect?v=1&tid=<<your analytics UA- tag>>&cid=$uid_got&t=pageview&dh=$host&dp=$uri&dr=$http_referer&uip=$remote_addr;
        }
}

```
Of course replace the `<<the domain you are using this on>>` and `<<your analytics UA- tag>>` with the appropriate data.  
This will result in the server sending out a GET request with the client's info to the tracking URL for each page visit. It increases bandwidth used by your server but is a neat trick regardless.
