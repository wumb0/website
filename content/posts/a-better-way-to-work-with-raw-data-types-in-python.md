Title: A Better Way to Work with Raw Data Types in Python
Date: 2017-03-11 11:12
Category: Programming
Tags: python ctypes
Slug: a-better-way-to-work-with-raw-data-types-in-python
Authors: wumb0

Working with raw data in any language can be a pain. If you are a developer there are many solutions to make it easier such as Google's Protocol Buffers. If you are a reverse engineer these methods can be too bulky especially if you are trying to quickly script an exploit (perhaps in a CTF where time is constrained). Python has always been my go-to language for exploit dev and general script writing but working with raw datatypes using just **pack** and **unpack** from the *struct* module is annoying and leaves much to be desired. I'm here to tell you that if you are still using **pack** and **unpack** for complex datatypes **there is a better way**.  

For the sake of this post we will attempt to work with the raw datatypes below defined as a C structures:  
```c
typedef struct __attribute__((packed)) NestedStruct_ {
    unsigned char flags[3];
    uint8_t val1;
    uint8_t val2;
} NestedStruct;

typedef struct __attribute__((packed)) ExampleNetworkPacket_ {
    uint16_t version;
    uint16_t reserved;
    uint32_t sanity;
    NestedStruct ns;
    uint32_t datalen;
    unsigned char data[0];
} ExampleNetworkPacket;
```

The total size of the **ExampleNetworkPacket** structure will be 17 bytes plus any data appended on it.  

As a side note I just recently learned that the last element of the **ExampleNetworkPacket** is valid C and is useful to be a pointer to the end of the structure instead of having to do this:  
```c
unsigned char data = (unsigned char*)(examplenetworkpacketptr + sizeof(ExampleNetworkPacket));
```

Neat.  
[[more]]

Moving on, let's say that you had reverse engineered this program and figured out these structures and named their fields. You set out to build a way to take raw data from a socket and get the fields of these structures. If you were using *struct*'s **pack** and **unpack** methods you would do something like this:  
```python
version, reserved, sanity, flags, val1, val2, datalen = unpack(">HHL3sccL", recvbuf)
data = recvbuf[16:]
```

This isn't too bad, actually. The more annoying part is putting one of these things back together...
```python
version, reserved, sanity, flags, val1, val2, datalen = 1, 0, 0x69696969, 1, 2, 3, len(data)
sendbuf = pack(">HHL3sccL", version, reserved, sanity, flags, val1, val2, datalen) + data
```

Still not too long but it's not clean and you can't easily have different instances like you can with real structs in C.  

Python's *ctypes* module can help you here. It has **LittleEndianStructure** and **BigEndianStructure** classes that will help turn the above code into something more usable and readable. **BigEndianStructure** is particularly useful for network protocols such as the one in the example.  

## Basic Structures ##
To get started import *ctypes* and make a class that inherits the **BigEndianStructure**. You'll want to import everything from the *ctypes* module to save you some typing.  
```python
from ctypes import *
class MyFirstStructure(BigEndianStructure):
    _pack_ = 1
    _fields_ = [ ('intfield', c_int),
                 ('bytefield', c_ubyte)]
```

This is a 5 byte structure equivalent to the following C code:  
```c
struct __attribute__((packed)) MyFirstStructure {
    int intfield;
    unsigned char bytefield;
};
```

Note the **packed** attribute in both snippets. This is important for the following reason:
```python
>>> m = MyFirstStruct()
>>> sizeof(m)
5
>>> class MyFirstStructure(BigEndianStructure):
...    _pack_ = 0
...    _fields_ = [ ('intfield', c_int),
...                 ('bytefield', c_ubyte)]
>>> m = MyFirstStruct()
>>> sizeof(m)
8
```
The packed structure has a size of 5 while the unpacked structure has a size of 8 because structure elements are always padded out to 4 bytes (on most common architectures) unless packed is specified. Eric Raymond has a great write up on structure packing [at his site](http://www.catb.org/esr/structure-packing/) if you want to know more about that. 

Packing becomes important for network protocols because if you have a byte and then an integer (32 bit) it will pad out the byte to 32 bits as well causing your structure type to be off.  

Setting attributes of the structure is as easy as just assigning values:  
```python
m = MyFirstStruct()
m.intfield = 1072
```

## Getting Raw Bytes and Making Structures from Raw Bytes ##
I love the book [Black Hat Python](https://www.nostarch.com/blackhatpython) by Justin Seitz. These particular extensions to the Structure class are based off of some of the code in Black Hat Python. It is talked about [here](http://bt3gl.github.io/black-hat-python-building-a-udp-scanner.html).  

We want to define a generic **NetStruct** class that we can make our structures inherit so they have useful traits:  
```python
class NetStruct(BigEndianStructure):
    _pack_ = 1

    def __str__(self):
        return buffer(self)[:]

    def __new__(self, sb=None):
        if sb:
            return self.from_buffer_copy(sb)
        else:
            return BigEndianStructure.__new__(self)

    def __init__(self, sb=None):
        pass
```
Lets break this down one function at a time:  
1. **\_\_str\_\_(self)** - When we call **str()** or **bytes()** on an instance of the structure we want it to return us the raw data from the structure. This makes it easy to send over a socket.  
2. **\_\_new\_\_(self)** - Creates the structure from a raw byte buffer or just makes a blank one.  
3. **\_\_init\_\_(self)** - This is needed to pass the input buffer (*sb*) to new if one is provided.  

With these functions overridden the structure is easier to convert to and from raw bytes.

## Building the Protocol ##
With knowledge of packing in mind lets build our **NestedStructure** first:  
```python
class NestedStruct(NetStruct):
    _fields_ = [('flags', c_ubyte*3),
                ('val1', c_ubyte),
                ('val2', c_ubyte)]
```
The feature of note here is that you can create arrays by just multiplying the type by the number of elements you need.  
This one was fairly simple. Now for the **ExampleNetworkPacket** structure:  
```python
class ExampleNetworkPacket(NetStruct):
    _fields = [('version', c_ushort),
               ('reserved', c _ushort),
               ('sanity', c_uint),
               ('ns', NestedStruct),
               ('datalen', c_uint)]
```
Two things to note here: first, we can nest structures by simply including another structure as an element and second data is missing! How do we define a field that has a variable length?

## Variable length fields ##
This is sort of where things get tricky. I was searching the internet for a solution to this problem and came across this [StackOverflow post](http://stackoverflow.com/questions/11634342/issues-about-resize-in-python-ctypes).

The code provided actually segfaulted python occasionally... so I ended up just going the simpler route: define the real array as a hidden variable and define the actual data attribute with a getter and setter to modify that array.  
```python
class ExampleNetworkPacket(NetStruct):
    _fields_ = [('version', c_ushort),
                ('reserved', c_ushort),
                ('sanity', c_uint),
                ('ns', NestedStruct),
                ('datalen', c_uint)]
    _data = (c_ubyte * 0)()

    @property
    def data(self):
        return str(buffer(self._data))

    @data.setter
    def data(self, indata):
        self.datalen = len(indata)
        self._data = (self._data._type_ * len(indata))()
        memmove(self._data, indata, len(indata))

    def __str__(self):
        return super(self.__class__, self).__str__() + self.data

```
There is a lot going on here. First, there is an internal data attribute *_data* that is the actual underlying *ctypes* array for the data. The *@property* tag makes it so you can reference data like an attribute (without parentheses). *@data.setter* defines what to do when you try setting the property attribute (i.e. pkt.data = "boo"). In this case when we access data we want it to return the raw bytes of *\_data* and when we set data we want it to create a new array of the same type but of the new size of the data. We also set the *datalen* attribute in the setter because it makes things more convenient. Finally, the **\_\_str\_\_** function has to be overridden to include the data on the end. Without it you would just get the header.  

## Testing it Out ##
```
>>> enp = ExampleNetworkPacket()
>>> enp.ns.flags[0] = 1
>>> enp.ns.flags[2] = 1
>>> enp.ns.val2 = 0xff
>>> enp.sanity = 0xabcd1234
>>> enp.version = 1
>>> enp.data = "hello world, nice struct"
>>> enp.datalen
24
>>> len(enp.data)
24
>>> enp.data
'hello world, nice struct'
>>> bytes(enp)
'\x00\x01\x00\x00\xab\xcd\x124\x01\x00\x01\x00\xff\x00\x00\x00\x18hello world, nice struct'
>>> enp2 = ExampleNetworkPacket(bytes(enp))
>>> enp.data
'hello world, nice struct'
```
Now it works exactly as you'd hope. It took a little work but the results are worth it!

## Bonus: Bitfields ##
*ctypes* also supports bitfields. Lets take the IP header as an example:
```python
class IP(Structure):
    _fields_ = [("ihl", c_ubyte, 4),
		("version", c_ubyte, 4),
		("tos", c_ubyte),
		("len", c_ushort),
		("id", c_ushort),
		("offset", c_ushort),
		("ttl", c_ubyte),
		("protocol_num", c_ubyte),
		("sum", c_ushort),
		("src", c_ulong),
		("dst", c_ulong)]
```
Here *ihl* and *version* are 4 bits each. The third element in the tuple is how many bits to use if not all of them.  
This makes *ctypes* structures even more powerful.
