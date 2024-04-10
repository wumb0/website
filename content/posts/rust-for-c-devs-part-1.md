Title: Rust for C Developers Part 1: Introduction
Date: 2024-04-10 13:37
Category: Programming
Tags: rust, windows, c
Slug: rust-for-c-devs-part-1
Authors: wumb0

Hello! It's been a while. Life has been very busy in the past few years, and I haven't posted as much as I've intended to. Isn't that how these things always go? I've got a bit of time to breathe, so I'm going to attempt to start a weekly(ish) blog series inspired by my friend scuzz3y. This series is going to be about Rust, specifically how to write it if you're coming from a lower level C/C++ background.  

When I first learned Rust, I tried to write it like I was writing C. That caused me a lot of pain and suffering at the hands of both the compiler and the `unsafe` keyword. Since then, I have learned a lot on how to write better Rust code that not only makes more sense, but that is far less painful and requires less `unsafe` overall. If you already know Rust, hopefully this series teaches you a thing or two that you did not already know. If you're new to Rust, then I hope this gives you a good head start intro transitioning your projects from C/C++ to Rust (or at least to consider it).  

I'm going to target this series towards Windows, but many of the concepts can be used on other platforms as well.  

Some of the topics I'm going to cover include (in no particular order):  

- Working with raw bytes  
- C structures and types  
- Shellcoding  
- Extended make (cargo-make)  
- Sane error handling  
- Working with native APIs  
- Working with pointers  
- Inline ASM  
- C/C++ interoperability  
- Building python modules  
- Inline ASM and naked functions  
- Testing  

If you have suggestions for things you'd like me to write about/cover, shoot me a message at [rustforcdevs@wumb0.in](mailto:rustforcdevs@wumb0.in).  

Expect the first post next week. It will be on working with pointers.  