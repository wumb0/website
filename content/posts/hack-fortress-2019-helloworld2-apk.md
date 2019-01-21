Title: Hack Fortress 2019 - helloworld2.apk
Date: 2019-01-21 11:45
Category: CTF
Tags: CTF, apk, reversing, hack fortress
Slug: hack-fortress-2019-helloworld2-apk
Authors: wumb0

![Final Score]({filename}/images/hack-fortress-finals/hackfortressfinal.jpg)

Another great year of Hack Fortress at Shmoocon!  
I wanted to do a post on this challenge in particular becuase it was one of two 300 point challenges on the board. I always get inside my own head about these challenges but I remind myself: **they are not normal CTF challenges**. These challenges are meant to be solved in just a few minutes, since the board is pretty big and the length of the competition is pretty short (30 min for prelims, 45 min for finals).  

I always focus on the Data Exploitation challenges because they usually have high point values and consist of android application reversing, basic binary reversing, macOS and image forensics (thanks [Sarah](https://twitter.com/iamevltwin)), obscure encoding, crypto (sometimes), and hardware, among other things. It's a very diverse but fun category. I solved three challenges totalling 525 points in this category in the finals. This particular challenge was the majority of those points, but actually took the least time since I've had experience with android application reverse engineering before.  

The challenge details were:
<pre>
Name: HelloWorld2
Location: helloworld2.apk
Points: 300
Desc: Find the encryption key
</pre>

Whenever I get an APK I do two things:  
<ul><li>Unpack it with [apktool](https://ibotpeaches.github.io/Apktool/)</li>
<li>Decompile it with [jad](http://www.javadecompilers.com/jad)/[JD-GUI](http://jd.benow.ca/)</li></ul>

Unfortunately my version of dex2jar was out of date so I had some issues with my automated decompilation tools. I ended up downloading the newest version of [dextools](https://github.com/pxb1988/dex2jar), running dex2jar, loading the jar into JD-GUI, and exporting the sources.  
Android apps always start with MainActivity, which was in the class path fortress/hack/helloworld2. The decompiled code is below.  

<pre><code class="java">package fortress.hack.helloworld2;

import android.os.Bundle;
import android.support.v7.app.AppCompatActivity;
import android.util.Base64;
import android.view.View;
import android.widget.EditText;
import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

public class MainActivity
  extends AppCompatActivity
{
  static
  {
    System.loadLibrary("native-lib");
  }
  
  public static String encrypt(String paramString1, String paramString2, String paramString3)
  {
    try
    {
      IvParameterSpec localIvParameterSpec = new javax/crypto/spec/IvParameterSpec;
      localIvParameterSpec.<init>(paramString2.getBytes("UTF-8"));
      paramString2 = new javax/crypto/spec/SecretKeySpec;
      paramString2.<init>(paramString1.getBytes("UTF-8"), "AES");
      paramString1 = Cipher.getInstance("AES/CBC/PKCS5PADDING");
      paramString1.init(1, paramString2, localIvParameterSpec);
      paramString1 = Base64.encodeToString(paramString1.doFinal(paramString3.getBytes()), 0);
      return paramString1;
    }
    catch (Exception paramString1)
    {
      paramString1.printStackTrace();
    }
    return null;
  }
  
  public void enceyptData(View paramView)
  {
    paramView = (EditText)findViewById(2131165238);
    ((EditText)findViewById(2131165239)).setText(encrypt(keyFromJNI(), getString(2131427370), paramView.getText().toString()));
  }
  
  public native String keyFromJNI();
  
  protected void onCreate(Bundle paramBundle)
  {
    super.onCreate(paramBundle);
    setContentView(2131296284);
  }
}
</code></pre>

We are looking for the encryption key. In the encrypt function the first paramter passed is the key. We know this because the first parameter to the init function of  *javax.crypto.spec.SecretKeySpec* is the key as bytes. Encrypt is called from MainActivity.enceyptData (sic) and the first parameter is keyFromJNI(). The function keyFromJNI has the prototype *public native String keyFromJNI();* which means that there is a native library in the application that will provide the key back to the java app.  
Native libraries for an android application can be found in the lib directory of the APK. The unpacked apk shows four different architectures in the lib directory: arm64-v8a, armeabi-v7a, x86, and x86\_64. I chose to look at the x86 version of *libnative-lib.so*, since [Hopper](https://www.hopperapp.com/) is better at x86 than other architectures (in my opinion).  
Since I have reverse engineered java native libraries before I know to look for the function name and/or class name in the function list. Pictured below is both the search and the decompiled function.  

![Hopper]({filename}/images/hack-fortress-finals/hopper-search.png)

Looks like the classic "build a string as integers" trick. I'm assuming sub\_61a0 is some kind of memory allocation function, and arg0 is always the [JNIEnv](https://docs.oracle.com/javase/7/docs/technotes/guides/jni/spec/functions.html) pointer, which contains a bunch of useful functions to convert C types into java types to return. I'm guessing the arg0+0x29c is either NewString or NewStringUTF. Moving forward I just took all of the hex bytes from the four integers that get put into the key buffer and unhexlified them. 

<pre><code class="python">In [26]: from binascii import unhexlify as unhex

In [27]: unhex("212b2b636f74746f47756f596563694e")
Out[27]: b'!++cottoGuoYeciN'
</code></pre>

Looks promising, but backwards...
<pre><code class="python">In [28]: unhex("212b2b636f74746f47756f596563694e")[::-1]
Out[28]: b'NiceYouGottoc++!
</code></pre>

And there's the flag!  
**NiceYouGottoc++**  
