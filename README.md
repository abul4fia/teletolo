# Teletolo
Telegram to Logseq

![](logo/teletolo.png)

# Purpose

This is an utility to download messages from Telegram and output them as markdown, suitable to be imported in logseq.

It can also write directly in the appropriate journal pages, based on the timestamp of the telegram messages.

## Features

* It can detect and automatically format some usual types of messages, such as:
  * **Images:** PNG, JPG, GIF (they are stored in the assets folder and inserted in the journal using `![](assets/file)` syntax).
  * **Audio:** ogg (they are stored in the assets folder and inserted in the journal using `![](assets/file)` syntax, which causes logseq to render an audio player with controls. Note that ogg audio format is not supported in iOS devices)
  * **Links:** if the link is to youtube or twitter, an appropriate embed is generated in the journal. If it is to a any other page, the title and excerpt of the page are retrieved and inserted in the journal.
  * **GPS location**. A bit of _hiccup_ code is inserted in the journal, to show the location in an embedded google map.
  * **Plain text**. The text is simply inserted in the journal. Of course you can include any tag or wikilink you want. The text is copied as is in the journal, and later interpreted by logseq appropriately.
* All these entries can be optionally timestamped (for interstitial journaling), using the time stamp of the moment you sent the message to Telegram, not the moment in which you run teletolo.
* Lots of configurable parameters in the `.teletolo.ini` file, so that you don't have to specify them in command line
* But all of them can be overriden by command line parameters (run teletolo with `--help` flag)

# Setup

## Python

You need Python 3.10 installed in your computer. It is also recomended that you create a virtual environment to install in it all required packages. To do this, you can for example write the following in a terminal (this is valid for a linux/MacOS machine):

```bash
$ python -m venv ~/venvs/teletolo
```

Remember to activate the virtual environment each time you create a new terminal to run teletolo

```bash
$ source ~/venvs/teletolo/bin/activate
```

To install the required packages run the following command after the virtual environment activation:

```bash
(teletolo) $ pip install -r requirements.txt
```

Test if all is working:

```bash
$ python route/to/this/repo/teletolo.py --help
```

## Telegram

To run teletolo you need to have a file called `.teletolo.ini` in the same folder in which you'll run the script. Usually this will be the folder in which your logseq graph is stored.

> If you use `git` remember to add `.teletolo.ini` to your `.gitignore` to avoid exposing this file in your graph repo, since it will contain sensible information.

A file named `teletolo.ini.sample` is provided. You have to rename it as `.teletolo.ini` and edit it to fill the required info, as explained below.

### Telegram credentials

You'll need to put in that file your phone number and your Telegram name, as well as your telegram api key and your telegram api key hash. These two last items can be obtained by accessing first to <https://my.telegram.org/auth> and then <https://my.telegram.org/apps>. If you already had these tokens for another app, you can use the same with teletolo.

### Telegram channels

By default teletolo will download the messages you sent to the channel named "Saved messages" in telegram.

If you prefer, you can create a new Telegram channel and change `channel_id` inside `.teletolo.ini` to put the numerical ID of the channel you created. This numerical ID can be obtained if you use <https://web.telegram.org/z> to navigate to your channel from a web browser. The final part of the url will show a string of digits. That's your channel id.

## Other options

You can read the file `.teletolo.ini` to set all the other options to your taste, but the default values provide a sensible behavior.

# First test

It is advised for the first test that you use the options `--apend_to_journal` and `--delete_after_download` to false. You can ensure that this is the case (despite the values especified in the `.teletolo.ini` file) by running teletolo with the following options:

```bash
(teletolo) $ python path/to/this/repo/teletolo.py -d0 -a0
```

The first ime you run teletolo, it will contact with the Telegram API to ask authorization to access your messages. After typing your phone number in teletolo, Telegram will send to that phone a code that you have to copy in the terminal when teletolo asks you for it. Once the authentication is correct, teletolo will create a file named `YourTelegramUser.session` which stores the credentials, so that you don't need to authenticate again the next time you run teletolo (unless you delete this file!). Remember to put this file in your `.gitignore` also.

If all is correctly configured, you'll see in the standard output the markdown of the messages retrieved from your Telegram channel. Also all media data (photos, audio) is downloaded to the current folder. The original messages are kept in the Telegram channel.

When you feel confident enough, you can change the options to `-d1`, to delete the messages from Telegram, after donwloading them, and `-a1` to append the messages to your journal in logseq. For the `-a1` option to work it is required that you run teletolo inside your graph folder. The files inside `./journals` corresponding to the dates in the downloaded messages will be modified (the new messages are appended at the end), and the multimedia, if present, will be stored in `./assets`.

If you want the options `-d1 -a1` to be permanent, you can set them in the `.ini` file. Remember that you can always override them from command line.

# Issues

In my use of this program I've found no issues, but of course I cannot guarantee that it is free of bugs. However, it will never delete messages in Telegram if the option `-d0` is used, and it will never alter your logseq files if the option `-a0` is used. Even when `-a1` is used, it will never delete any logseq file, and all the changes in the journal files will be to append data, never to replace it. It will overwrite however the downloaded media, but since the name of the file is based on the timestamp of the telegram messages, the probability of filename collision is zero for all practical purposes.

If you run on any other kind of problem or you find that some messages in your telegram channel are being skipped by teletolo, please open an issue in this repo. Telegram supports a good number of message types, and I implemented in teletolo only the few ones I've found more useful to me (mostly plain text, web links, images, audio notes, and gps coordinates)
