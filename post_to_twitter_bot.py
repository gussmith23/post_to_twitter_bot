import telebot
import configparser
import tweepy
import logging
import re
from telebot import types

character_limit = 280

logging.basicConfig(level = logging.DEBUG)

user_prefs_section_name = "user preferences"

config_path = "post_to_twitter_bot.cfg"
config = configparser.ConfigParser()
config.read(config_path)

bot = telebot.TeleBot(config['telegram_bot_api']['telegram_token'])

auth = tweepy.OAuthHandler(config['twitter_api']['consumer_key'],
                            config['twitter_api']['consumer_secret'])
auth.set_access_token(config['twitter_api']['access_token'],
                      config['twitter_api']['access_token_secret'])
api = tweepy.API(auth)  

open_requests = {}
open_votes = {}

def use_nickname(user):
  logging.info(user.username[-3:].lower())
  user_is_bot = user.username is not None and user.username[-3:].lower() == "bot"
  return not user_is_bot

def must_vote(user):
  user_is_bot = user.username is not None and user.username[-3:].lower() == "bot"
  return not user_is_bot

@bot.message_handler(commands=['setnick'])
def handle_setnick(message):
  nick = message.text
  # TODO(gus) lots of hardcoding
  nick = re.sub("/setnick", "", nick)
  nick = re.sub("@post_to_twitter_bot", "", nick)
  nick = nick.strip()
  
  logging.info("Setting user {0}'s nickname to {1}.".format(message.from_user.id, nick))

  if user_prefs_section_name not in config:
    config.add_section(user_prefs_section_name)
  config.set(user_prefs_section_name, str(message.from_user.id), nick)

  # TODO(gus) writing every time?
  with open(config_path, "w") as config_file:
    config.write(config_file)

@bot.message_handler(commands=['post'], 
                      func=lambda m: (m.from_user.id , m.chat.id) not in open_requests
                                      and m.forward_date is None)
def handle_post_step1(message):
  request_id = (message.from_user.id , message.chat.id)
  logging.info("New request from " + str(request_id))
  open_requests[request_id] = []
  bot.reply_to(message, "Alright, now forward the messages you'd like me to post.")

def post(request_id):
  messages = sorted(open_requests[request_id], key=lambda m: m.date)

  # Create tweet.
  output = "\n".join([ (config[user_prefs_section_name][str(m.forward_from.id)] if use_nickname(m.forward_from) else m.forward_from.first_name) + ": " + m.text for m in messages])
  logging.info("MESSAGE TO TWEET:\n" + output + "\nEND OF MESSAGE")
  if len(output) <= character_limit:
    api.update_status(output)
  else:
    continuation_string = "[..]"
    segment_length = character_limit - len(continuation_string)
    segments = [output[i:i+segment_length] for i in range(0, len(output), segment_length)]
    for i in range(len(segments)-1):
      segments[i] += continuation_string
    for tweet in segments:
      api.update_status(tweet)

  """ Finish this later.
  tweets = []
  current_tweet = ""
  for m in messages:
    formatted = m.from_user.first_name + ": " + m.text

    # case 1: tweet is nonempty, new message fits
    if current_tweet and len(current_tweet) + 1 + len(formatted) < character_limit:
      current_tweet += "\n" + formatted
    
    # case 2: tweet is empty, new message fits
    elif not current_tweet and len(formatted) < character_limit:
      current_tweet += formatted

    # case 3: new message doesn't fit
    else:
      # first, we complete the current tweet.
      tweets.append(str(current_tweet)) #TODO(gus): missing python knowledge
      current_tweet = ""
  """
    

  # TODO(gus) synchronization?
  if request_id in open_requests: del open_requests[request_id]
  if request_id in open_votes: del open_votes[request_id]

@bot.message_handler(commands=['post'], 
                      func=lambda m: (m.from_user.id , m.chat.id) in open_requests
                                      and m.forward_date is None)
def handle_post_step2(message):
  request_id = (message.from_user.id , message.chat.id)
  messages = sorted(open_requests[request_id], key=lambda m: m.date)

  # Check that all users have set their nickname preference.
  users_without_nicknames = set()
  for m in messages:
    if use_nickname(m.forward_from):
      if user_prefs_section_name in config \
          and str(m.forward_from.id) in config[user_prefs_section_name]:
        pass
      else:
        users_without_nicknames.add(m.forward_from)
  if len(users_without_nicknames) > 0:
    bot.reply_to(message, "The following users have not set their nickname: " +
                    " ".join(["[{0}](tg://user?id={1})".format(u.first_name, 
                                                              u.id) 
                              for u in users_without_nicknames]) +
                    # TODO(gus) hardcoded command
                    ". Please set your nickname with the /setnick command.",
                    parse_mode = "Markdown")
    return

  # Start vote.
  vote_set = set()
  for m in messages:
    if must_vote(m.forward_from):
      vote_set.add(m.forward_from.id)
  if len(vote_set) == 0: 
    post(request_id)
  else:
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton(callback_data="yes", text="yes"),
                types.InlineKeyboardButton(callback_data="no", text="no"))
    out = bot.send_message(message.chat.id, "Should I post these messages?",
        reply_markup=markup, parse_mode="Markdown")

    open_votes[out] = {
      'set' : vote_set,
      'request_id' : request_id
    }

@bot.callback_query_handler(func=lambda call: call.message.message_id in open_votes)
def call(call):
  logging.info("Got callback query for message " + str(call.message.message_id))
  request_id = open_votes[call.message.message_id]['message_id']
  if (call.data is "no"):
    # TODO(gus) put this in a function
    if request_id in open_request: del open_request[request_id]
    if request_id in open_votes: del open_votes[request_id]
    return

  open_votes[call.message.message_id]['set'].remove(call.from_user.id)
  if len(open_votes[call.message.message_id]['set']) == 0:
    post(request_id)

@bot.message_handler(func=lambda m: m.forward_date is not None
                                    and (m.from_user.id , m.chat.id) in open_requests)
def handle_forward(message):
  request_id = (message.from_user.id , message.chat.id)
  logging.info("Got forward for open request from " + str(request_id))
  open_requests[request_id].append(message)

"""
@bot.message_handler()
def post_to_twitter(message):
  print("Tweeting: " + message.text)
  api.update_status(message.text)
"""

logging.info("Bot started!")
bot.polling()						# Bot waits for events.

