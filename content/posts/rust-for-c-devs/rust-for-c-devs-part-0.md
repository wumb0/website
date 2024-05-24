Title: Rust for C Developers Part 0: Introduction
Date: 2024-04-10 13:37
Category: Programming
Tags: rust, windows, c
Slug: rust-for-c-devs-part-0
Authors: wumb0

Hello! It's been a while. Life has been very busy in the past few years, and I haven't posted as much as I've intended to. Isn't that how these things always go? I've got a bit of time to breathe, so I'm going to attempt to start a periodic blog series inspired by my friend scuzz3y. This series is going to be about Rust, specifically how to write it if you're coming from a lower level C/C++ background.  

When I first learned Rust, I tried to write it like I was writing C. That caused me a lot of pain and suffering at the hands of both the compiler and the `unsafe` keyword. Since then, I have learned a lot on how to write better Rust code that not only makes more sense, but that is far less painful and requires less `unsafe` overall. If you already know Rust, hopefully this series teaches you a thing or two that you did not already know. If you're new to Rust, then I hope this gives you a good head start into transitioning your projects from C/C++ to Rust (or at least to consider it).  

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
**(Update: 4/20/24)**: I decided to expand this post to cover some background first before doing the post on pointers. So that is still in the works!  

All posts in the series (so far):

- [Introduction (this post)]({filename}rust-for-c-devs-part-0.md)
<!-- - [Pointers]({filename}rust-for-c-devs-part-1.md) -->

There is also a github repository that goes along with this series. You can find that [here](https://github.com/wumb0/rustforcdevs).

[[more]]

# Rust Basics
Before you get going on the whole series, make sure you understand a few basic Rust concepts. You should read the [Rust book](https://doc.rust-lang.org/book/) to get a basic handle on how the language works, but I have also included an introduction to some concepts and coding styles I'll be using in the posts moving forward.  

Rust 1.76.0 (07dca489a 2024-02-04) was used as a reference for this post, so keep that in mind if it's 2077 and you're reading this for some reason.  

## Mutability
By default, declared variables in Rust are *immutable*. This is the opposite of how C works, where variables are assumed mutable unless you declare them `const`. In order to declare a mutable variable, you must use the `mut` keyword. 
For example:

```rust
let mut x = 2;
x = 3; // ok! x is mutable
let y = 2;
y = 3; // error, y is not mutable
// variable rebinding is possible, also
let mut y = 2;
y = 2; // ok! y is mutable now because of the rebind
```

## Scope
Rust has strict scoping rules like C. For example, the following will error:  

```rust
{
    let mut x = 3;
}
x = 5; // x is not defined, it went out of scope!
```

To make this work you would do the following:
```rust
let mut x;
{
    x = 3;
}
x = 5; // x was declared in the outer scope, so this is fine
```

## Basic Types
Rust has a number of basic (primitive) types you should be aware of. I have also included the equivalent C types for quick reference.  

| Rust Type | Size (bytes) | Equivalent C Type(s) |
|-----------|--------------|----------------------|
| u8    | 1  | unsigned char, BYTE, uint8_t |
| i8    | 1  | char, int8_t |
| char  | 4  | char32_t (technically...) |
| bool  | 1  | bool |
| u16   | 2  | unsigned short, WCHAR, uint16_t | 
| i16   | 2  | short, int16_t |
| u32   | 4  | unsigned int, DWORD, ULONG, uint32_t |
| i32   | 4  | int, BOOL, NTSTATUS, LONG, int32_t |
| f32   | 4  | float |
| u64   | 8  | uint64_t, DWORD64, ULONGLONG, unsigned long† |
| i64   | 8  | int64_t, long†, LONGLONG |
| f64   | 8  | double |
| u128  | 16 | uint128_t |
| i128  | 16 | int128_t |
| usize | 8† | size_t, uintptr_t |
| isize | 8† | ssize_t |
| ()    | 0  | N/A |

† This is the size of the type on amd64

One important note about types is that the default type of a bare integer is `i32`, much like in C, where the default bare integer type is `int`. You can specify the integer type explicitly by suffixing the number with it (ex. `1usize`). 
For `bool`, use `true` and `false`.  

For `char`, you can use the same syntax as in C (ex. `'A'`).  

For bytes (`u8`), you can prefix the `char` string with a `b` (ex. `b'A'`).  

The *unit struct* or `()` is a special zero sized type that just represents nothing.  

### References
References and pointers may seem similar, but they are different. References are tracked by the compiler's lifetime manager, while pointers are not. In Rust, you get a reference via the `&` or `&mut` operators. One gets an *immutable* reference and the other gets a *mutable* reference. You will see the term *borrowing* used to refer to references sometimes. The compiler has a few rules relating to references to help ensure safety. Violating any of these rules will result in a **compiler error**:  

1. An object's reference cannot out-live the original object.  
2. An object may have an unlimited number of *immutable* references **OR** exactly one *mutable* reference.  
3. In order to get a mutable reference to an object it must be declared `mut`able.  

#### Lifetimes
A lifetime is how long an object lasts. All objects have lifetimes associated with them. Most of the time, the compiler can infer (elide) the lifetime of the object or reference. When it cannot, you will need to declare the lifetime explicitly. Lifetimes are one of the hardest things for new Rust developers to grasp and work around, especially when coming from C, where lifetimes are managed almost entirely by the programmer.  

Think about this case in C:

```c
int *myfunc() {
    int mystackint = 55;
    return &mystackint;
}
```

A classic mistake by the inexperienced C developer.  

![bad time]({static}/images/rust-for-c-devs/badtime.jpg)

In Rust, that will result in an error because the reference will outlive the stack variable.  

<iframe src="https://play.rust-lang.org/?version=stable&mode=debug&edition=2021&code=fn+myfunc%3C%27a%3E%28%29+-%3E+%26%27a+u32+%7B%0A++++let+mystackint+%3D+55%3B%0A++++return+%26mystackint%3B%0A%7D" style="width: 100%; height: 500px;"></iframe>

The `'a` is a bit confusing. You will sometimes see the following syntax:  
```rust
struct MyStruct<'a> {
    myref: &'a u32
}
```

This is just saying "`myref` must live at least as long as `MyStruct`". In the case of `myfunc<'a>` above it's just saying that the returned reference will last as long as the function, which is fairly obvious, but necessary. You could also say `'static` which means that it is a static reference and will last as long as the program runs.   

There is much more to say on lifetimes, but I'm going to stop here. They will take practice! I will make sure to explain any lifetime specific stuff I need to throughout these posts.  

## Complex Types
### Arrays, Slices, and Strings
An array is a fixed length series of elements. The size must be known at compile time.  

A slice represents a series of bytes with a size that may or may not be known at compile time. That series of bytes is just a pointer to an array and a number of elements; they are array references. Slices are useful because they can be used as a common type to represent static/fixed or dynamically allocated sequences of items as well as sub-arrays (slices). Arrays can be coerced into the slice type by indexing (slice-ing) or by using the `as_slice` method. The length of a slice can be obtained with the `len` method. Like arrays, slices also can be mutable or immutable.  

```rust
// make a fixed size array
let arr = [0, 1, 2, 3, 4];
// take a slice of the array
let slice: &[u32] = &arr[2..];
assert_eq!(slice.len(), 3);
```

There is a special kind of slice called a `&str` that is a specialized `&[u8]` that is `UTF-8` aware. It is used to represent strings. It is the common implementation between static/fixed and dynamically allocated strings. Again, it is just a start pointer and a length.  

### Owned vs. Referenced Types
For static strings and arrays slices and the `&str` type are fine. These are *referenced* types, where someone else is responsible for the memory that the data within them occupies. If you want an object that owns and allocates these types, then you need an *owned* type. To "own" the memory backing the type is to be responsible for allocating, reallocating, and eventually freeing the underlying memory backing the information. Below are some owned types and their referenced counterpart:

- `String` - `&str`  
- `Vec<T>` - `&[u8]`  
- `Box<[T]>` - `&[u8]`  
- `Path` - `PathBuf`  

All of those owned types can be turned into their reference types with convenience methods provided with each one. The inverse is also true. Sometimes you'll see the `ToOwned` and `AsRef` (or sometimes `Borrow`) traits implemented for a type. If you have a reference type and want the owned type, you may be able to call `to_owned` on the reference object to allocate an owned version or `as_ref` (or `borrow`) on the owned object in order to get the reference/borrowed version.  

## Structs, Enums, and Unions
Structs work pretty similar in Rust and C. It is a collection of types in a unit. Much like a C++ struct, you can write methods to interact with its attributes. One thing you should be aware of is that Rust structure packing rules are different than C structure packing rules. The Rust compiler may actually re-order structure variables at its discretion unless you tell it not to. To make sure C structure packing rules are followed, you can tag a struct as `repr(C)`

```rust
#[repr(C)]
struct MyStruct {
    member1: u32,
    member2: u64,
    member3: u8,
    member4: u16,
}
```

You can also tag a struct with `repr(packed)` to pack a structure like you would with `__attribute__((packed))` or `#pragma pack`.  
The [Rust reference](https://doc.rust-lang.org/reference/type-layout.html) has a section on type layouts that is particularly useful.  

Enumerations in Rust are special because they can optionally contain data types. For example:

```rust
enum MyEnum {
    NoData,
    HasString(String),
    HasInt(i32),
}
```

To determine which variant you have, you can use a `match` statement. Keep in mind that in Rust, all cases **must** be covered in a `match`.  

```rust
let myenum = MyEnum::NoData;
match myenum {
    MyEnum::NoData => println!("No Data!"),
    MyEnum::HasString(s) => println!("The string was {s}"),
    MyEnum::HasInt(i) => {
        let x = i + 5;
        println!("The integer (plus 5) was {x}");
    }
}
```
You can also implement methods on enums in Rust.  

Finally, unions exist in Rust mostly for C compatibility/FFI. Anywhere I would normally use a union in C I would just use a Rust enum with encapsulated types. Accessing data within an enum is unsafe. 

### Option and Result
Two useful Rust enums are the `Option` and `Result` types. Their definitions are simple:

```rust
pub enum Option<T> {
    Some(T),
    None
}

pub enum Result<T, E> {
    Ok(T),
    Err(E)
}
```

The `Option` type is what inspired C++17's `std::optional` type; it is either something or nothing.  

The `Result` type is either a success value (`Ok`) or an error value (`Err`). 

#### The `?` Operator
`Result` and `Option` have a special power: the `?` operator. In C/C++ how many times have you found yourself writing the following pattern?

```c
void *someFunction() { /* do something */ }
bool stuff() {
    void *result = someFunction();
    if (NULL == result) {
        return false;
    }
    // do something with x

    return true; // return the success case
}
```

In Rust, when using `Result` or `Option` you can reduce that error checking logic down to one single character: `?`.  

```rust
fn someFunction() -> Option<*mut c_void> { /* do something */ }
fn stuff() -> Option<()> {
    // if someFunction returns None, then return None
    let x: *mut c_void = someFunction()?;
    // do something with x

    Some(()) // return the success case
}
```

Basically, if `someFunction` returns `None`, `?` will propagate that error up, returning it immediately. If it returns `Some()` then the value from the `Some()` will be extracted and the code continues. `Result` and `?` work the same way, so you can have a verbose error type returned instead of just a generic failure (`None`).  

We will talk much more about error handling and use of `Result` and `Option` in a future post!  

## The `unsafe` Keyword
All it means is that the compiler cannot guarantee the safety of the code contained within. It does not mean that the code **will** crash, it just means that it **could** crash. The caller needs to ensure that they are using `unsafe` functions or operations carefully. This does not mean that the result of an `unsafe` block will always be valid. You may cause a crash in a "safe" section of code when using the result of an `unsafe` operation. For example:  

<iframe src="https://play.rust-lang.org/?version=stable&mode=debug&edition=2021&code=fn+main%28%29+%7B%0A++++let+disaster%3A+%26u8+%3D+unsafe+%7B+std%3A%3Amem%3A%3Atransmute%281usize%29+%7D%3B%0A++++println%21%28%22Ok%21%22%29%3B%0A++++%2F%2F+crash+here%0A++++println%21%28%22Disaster%21+%7B%7D%22%2C+*disaster%29%3B%0A%7D" style="width: 100%; height: 500px;"></iframe>

When will you see `unsafe` used?  

- Dereferencing a pointer. As we will cover in the next post, the validity of a pointer cannot be guaranteed, so dereferencing it is inherently dangerous   
- Calling any `extern` or FFI function. Since it it is not Rust code, the compiler cannot guarantee its safety!  
- Implementing the `Send` and `Sync` traits. You can tell the compiler that your type is transferrable (sendable) between threads (`Send`) and/or usable by multiple threads simultaneously (`Sync`). If you are wrong, then that type may cause a crash.  
- Union access  
- Mutable static variable access  

You can also mark entire functions `unsafe`, which just declares the whole thing as an `unsafe` block. In other words, you will not need to wrap dangerous operations (such as dereferencing a pointer) in `unsafe`. That would be redundant and the compiler would tell you it is unneeded.  When you declare a function `unsafe`, the compiler will issue a warning if there is no comment explaining why via a section comment denoted by the `# Safety` header. For example:

```rust
/// A dangerous function
/// # Safety
/// Pointer dereference! Without this comment section the compiler will issue a warning
unsafe fn danger(ptr: *mut u8) -> u8 {
    *ptr
}
```

When you call the function `danger` you will be required to call it with an `unsafe` block. 

```rust
let myu8 = unsafe { danger(u8ptr) };
```

## Generics
C++ has templating. C has... macros? Rust has generics. You can make a struct, enum, trait, etc. generic over a type. That looks like this:  

```rust
struct MyStruct<T> {
    mything: T,
}

impl<T> MyStruct<T> {
    fn new(thing: T) -> MyStruct<T> {
        MyStruct { mything: thing }
    }
}
```

Here's an example of a generic function:  
```rust
fn myfunc<T>(thing: &T) {
    // do something with the thing reference
}
```

You can specify multiple generics too. Just separate them with commas (ex. `fn myfunc<A, B, Sea, Dee>`).  

## Traits
A trait is a set of functions, attributes, and/or types that a type can implement. Think of it like a protocol or (abstract) base class. All implementors of a trait can use any of it's methods/types/attributes. An example trait from the standard library:

```rust
pub trait TryFrom<T>: Sized {
    type Error;

    // Required method
    fn try_from(value: T) -> Result<Self, Self::Error>;
}
```

This shows a few things: a generic (`T`), a required trait bound (`Sized`), an associated type (`Error`), and a required method `try_from`. This means that if you want to implement `TryFrom` to attempt to convert type A to type B you would do the following:
```rust
impl TryFrom<A> for B {
    type Error = String;
    fn try_from(value: A) -> Result<Self, Self::Error> {
        // try the conversion....
        todo!();

        // return a Result
        if conversion_success {
            Ok(new_b)
        } else {
            Err(String::from("Conversion failed!"))
        }
    }
}
```

Now, if we have an instance of A, we can call the `try_from` method on it in order to convert to type B. If there are multiple `TryFrom` implementations for B, then you just need to specify the type explicitly. Let's say we have a `TryFrom<A>` implemented for `C` also. 

```rust
let my_a = A;
let my_b = my_a.try_from::<B>().unwrap();
// OR
let my_b: B = my_a.try_from::<B>().unwrap();
```

On failure, the `Conversion failed` message will print.  

A required trait bound means that anything that implements that trait must also implement the other trait(s) specified (ex. `Sized` from above). What this means is that if a type implements that trait, it ALSO implements the required trait bounds so you can call the methods from those other required traits as long as you import the trait.  

<div class="uk-alert">
    <i class="fa fa-info-circle fa-lg"></i><span class="alert-text">If the conversion is infallible (always succeeds), then you would want to implement the `From<T>` trait instead.</span>
</div>

If we look at another, more complicated trait from the standard library (BufRead), we can see a more useful required trait bound: 
```rust
pub trait BufRead: Read {
    // Required methods
    fn fill_buf(&mut self) -> Result<&[u8]>;
    fn consume(&mut self, amt: usize);

    // Provided methods
    fn has_data_left(&mut self) -> Result<bool> { ... }
    fn read_until(&mut self, byte: u8, buf: &mut Vec<u8>) -> Result<usize> { ... }
    fn skip_until(&mut self, byte: u8) -> Result<usize> { ... }
    fn read_line(&mut self, buf: &mut String) -> Result<usize> { ... }
    fn split(self, byte: u8) -> Split<Self>
       where Self: Sized { ... }
    fn lines(self) -> Lines<Self> 
       where Self: Sized { ... }
}
```

Anything that implements `BufRead` must implement read, which looks like this:
```rust
pub trait Read {
    // Required method
    fn read(&mut self, buf: &mut [u8]) -> Result<usize>;

    // Provided methods
    fn read_vectored(&mut self, bufs: &mut [IoSliceMut<'_>]) -> Result<usize> { ... }
    fn is_read_vectored(&self) -> bool { ... }
    fn read_to_end(&mut self, buf: &mut Vec<u8>) -> Result<usize> { ... }
    fn read_to_string(&mut self, buf: &mut String) -> Result<usize> { ... }
    fn read_exact(&mut self, buf: &mut [u8]) -> Result<()> { ... }
    fn read_buf(&mut self, buf: BorrowedCursor<'_>) -> Result<()> { ... }
    fn read_buf_exact(&mut self, cursor: BorrowedCursor<'_>) -> Result<()> { ... }
    fn by_ref(&mut self) -> &mut Self
       where Self: Sized { ... }
    fn bytes(self) -> Bytes<Self>
       where Self: Sized { ... }
    fn chain<R: Read>(self, next: R) -> Chain<Self, R>
       where Self: Sized { ... }
    fn take(self, limit: u64) -> Take<Self>
       where Self: Sized { ... }
}
```

Lots of methods! So anything that implements `BufRead` must also implement `Read` so you can call `read_to_end` no problem. You might also notice that there are "provided methods` in both of those traits. This means that a default implementation is provided, but you may override the methods if you choose!  

You can enforce trait bounds on a generic too. This can either be done in the struct definition, or you can have different implementations for different traits!
```rust
use std::io::Read;
struct MyStruct<T: Read> {
    readable: T,
}

impl<T: Read> MyStruct<T> {
    fn new(readable: T) -> MyStruct<T> {
        Self { readable }
    }
}

impl<T: Read + Debug> MyStruct<T> {
    fn print_object(&self) {
        println!("{:?}", self.readable);
    }
}
```

Pretty neat!  

## Project Layout
The standard Rust project looks like this:

- project_dir  
  - Cargo.toml - describes your project, how to build it, what to build, and what dependencies it uses  
  - src - contains all of your source code  
    - lib.rs / main.rs - the entry file for a binary (main.rs) or library (lib.rs)  
    - submodule1.rs - for code organization you can define submodules inline in code, in it's own file, or in it's own folder (next)  
    - submodule2 - larger submodules can be put into folders  
      - mod.rs - a submodule in a folder must have a mod.rs to be seen by the compiler  
    - bin - a directory containing additional projects to build as binaries. each must contain a `main` function  
      - binary1.rs  
      - binary2.rs  
  - build.rs - optional build script to modify how the package is built  
  - target - automatically generated by `cargo`. stores build artifacts  
  - .cargo  
    - config.toml - additional configuration options  

### Workspaces
I like to use [cargo workspaces](https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html) for my projects. They end up looking like this:  

- project_dir  
  - Cargo.toml  
  - crates  
    - lib1
      - Cargo.toml
      - src  
        - lib.rs
    - lib2
      - Cargo.toml  
      - src  
        - lib.rs  
    - binary  
      - Cargo.toml  
      - src  
        - main.rs
  - tests - integration tests (more on testing later)  
    - Cargo.toml  
    - src  
      - lib.rs

The top level Cargo.toml looks like this:

```toml
[workspace]
members = ["crates/*", "tests"]
resolver = "2"

[workspace.package]
edition = "2021"
version = "0.1.0"
authors = ["wumb0"]

[workspace.dependencies]
log = "0.4"
```

And then one of the sub-project Cargo.toml files would look like this:
```toml
[package]
name = "lib1"
edition.workspace = true
version.workspace = true
authors.workspace = true

[dependencies]
log.workspace = true
```

So you can define shared metadata between all of your projects including the Rust edition, package version, package author(s), and even dependencies. You can also define build profiles in the top-level workspace Cargo.toml.  

## Building
To build a project in Rust, run `cargo build`. The default build profile is `debug`. To specify the release target use the `--release` flag to `cargo build`. You can also create additional profiles in your project's Cargo.toml and specify the alternative profile with the `-p` option to `cargo build`. To specify the target (I like to cross compile from my M3 Macbook to Windows on amd64), you can specify the target on the command line via the `--target` option, providing the target triple. To list all target triples run `rustup target list`. To install a new target run `rustup target add <target triple>`.  

To use certain features of Rust that are considered "unstable", you must use the "nightly" toolchain, as opposed to the "stable" toolchain. To install the nightly toolchain you can use the `--toolchain nightly` option to `rustup target add`. To set the default toolchain to nightly run `rustup default nightly`. To use the nightly toolchain without setting it to default you must use the `+nightly` option to `cargo` before each subcommand. For example, if I wanted to build using the nightly toolchain I would run `cargo +nightly build`.  

A few notable nightly features that I use frequently are:  

- `build-std` / `build-std-features` - A cargo option to allow you to build the Rust standard/core libraries from source, potentially changing features. Rust includes very verbose error messages in its binaries, even in release mode. These are known as *panic strings*. If you want to compile them out for whatever reason and just have the program crash instead you can build the Rust core/std with the `panic_immediate_abort` feature. If you want Rust's versions of `memcpy`, `memset`, and friends you can specify the `compiler-builtins-mem` feature flag to `build-std-features`. We will talk about `build-std` a lot more in future posts.  
- `remap-cwd-prefix` - A rustflag (flag that is passed to `rustc`, the Rust compiler) to allow you to remap the cwd in the binary to something else. Useful to get your username and project path out of the final binary. Really you should just be building in a docker container, so you might not need this.  
- `profile-rustflags` - A Cargo.toml feature to allow you to specify rustflags per build profile.  

There are more, but those are good examples of 3 different places unstable features might be used. I don't use unstable features in my code directly so much, but if you need to enable one you just have to specify it at the top of your `lib.rs`/`main.rs` for your crate: `#![feature(coroutines, coroutine_trait)]` as an example to enable the `coroutines` and `coroutine_trait` features.  

### Creating DLLs
To create a Windows DLL out of a Rust library, add the following section to your project's Cargo.toml:

```toml
[lib]
crate-types = ["cdylib"]
```

<div class="uk-alert uk-alert-warning">
    <i class="fa fa-exclamation-triangle fa-lg"></i><span class="alert-text">If you declare a crate to be a <code>cdylib</code> you might have trouble testing it. <code>cargo test</code> will try to run the produced DLL as an EXE, which will not work. To avoid this issue, write your tests in a separate module and then include it as a library in your <code>cdylib</code> crate. Or don't write tests... up to you!</span>
</div>

## `std` and `core`
The Rust standard library has a lot of useful, platform dependent features. It is also completely optional to use. If you are writing to a platform that does not have standard library support or you simply do not need/want the standard library, you can compile your crate with the `no_std` attribute. With `no_std` you may use functionality within the Rust `core` module. You can also use the `no_core` attribute in your module, but I've never seen a practical use for that...  

What if you can't or don't want to use the standard library, but you do want nice things like dynamically allocated strings and vectors? Well, you can define a custom allocator and use the `alloc` crate. We will cover that more in its own post, but it's pretty cool functionality.  

All items inside of `core` and `alloc` are included in the top level namespace of `std`. For example, both `core::arch::asm` and `std::arch::asm` resolve to the same `asm!` macro inside of core. Same with `core::ffi::c_int` and `std::ffi::c_int`. You get the idea.  

## Macros
Rust supports two different types of macros: regular macros and procedural macros. Regular macros are akin to C (`#define`) macros. Procedural macros are sort of like C++'s `constexpr` but have way more functionality. Writing either of these macros presents unique challenges, but they are at least a bit more versatile than C macros and a bit more sane due to "*macro hygiene*".  

Macros may take a few different forms, but the most common syntax (and the only one for regular macros) is `macro_name!`. Yep, that's right, `println!` is a macro. Rust does not support variadics (except for C FFI), so a macro must be used.  

## Panicking, `unwrap`, and `expect`
If something goes wrong in a Rust program, it may either choose to propagate the error up or **panic**. You can trigger a panic explicitly via the `panic!` macro. You can also do so accidentally by doing something like accessing a non-existent array element or dividing by zero. When a program panics it will print that it panicked, where, and why. Sometimes it will also print a stack trace, which can be useful to track down the issue.  

Some types such as `Option` and `Result` have functions that can trigger panics on failure. The `unwrap` and `expect` functions are examples of functions that will panic when invoked with a `None` or `Err` return. `unwrap` will display the error contained within the `Result::Err` enum, and `expect` will display the string that is passed into it.  

A panic should only be triggered on a completely unrecoverable case, such as one where it would be dangerous to continue. Library code should almost never panic. Always propagate the error upward via a `Result`, `Option`, or other vessel and let the application developer decide how to deal with it. They could recover and try again, for all you know!  

## Basic FFI
I will do a while post of FFI and C/C++ interoperability, but I wanted to cover basic function importing here, because I will be using it in Part 1 <!-- [Part 1]({filename}rust-for-c-devs-part-1.md). -->  

### FFI Types
If you need explicit FFI types, you can use the `core::ffi` module (a.k.a. `std::ffi`).  
If I am translating a call from C to Rust I will usually just use the Rust types instead of using FFI types. You'll see that below.  

### Importing External Functions
```rust
use core::ffi::c_void;
// Using *const u8 for char * and *mut c_void for HMODULE
#[link(name = "kernel32")]
extern "system" {
    fn GetModuleHandleA(*const u8) -> *mut c_void;
    fn GetProcAddress(*mut c_void, *const u8) -> *mut c_void;
}
```

### Passing Strings
You need to remember that Rust strings are **not** NULL terminated. In order to pass a string to a function that expects a NULL terminated C-string, you need to explicitly add the NULL. This is also true for wide/unicode C-strings. You'll also need to pass the string as a pointer via the `as_ptr` function of the `String` or `str` types.  

For example:
```rust
let ntdll = unsafe { GetModuleHandleA("ntdll\0".as_ptr()) };
let mut funcname = String::from("NtQueryInformationProcess");
funcname.push(0);
let ntqueryinformationprocess = GetProcAddress(ntdll, funcname.as_ptr());
```

If you have a `str` you need to NULL terminate, just use `to_string` and then `push` a NULL.  You can also use the `format!` macro:
```rust
let mystr = "hello world";
let myntstr: String = format!("{mystr}\0");
```

We will also cover the `CStr` type in a future post!

# Wrapping Up
That should be the basics you need. Again, I recommend reading the Rust Book as well to get a better grasp on things.  

Look forward to the next post in the series soon.  