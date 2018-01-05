import telebot
import configparser
import tweepy
import logging

character_limit = 280

logging.basicConfig(level = logging.DEBUG)

config = configparser.ConfigParser()
config.read("post_to_twitter_bot.cfg")

bot = telebot.TeleBot(config['telegram_bot_api']['telegram_token'])

auth = tweepy.OAuthHandler(config['twitter_api']['consumer_key'],
                            config['twitter_api']['consumer_secret'])
auth.set_access_token(config['twitter_api']['access_token'],
                      config['twitter_api']['access_token_secret'])
api = tweepy.API(auth)  

open_requests = {}

@bot.message_handler(commands=['post'], 
                      func=lambda m: (m.from_user.id , m.chat.id) not in open_requests
                                      and m.forward_date is None)
def handle_post_step1(message):
  request_id = (message.from_user.id , message.chat.id)
  logging.info("New request from " + str(request_id))
  open_requests[request_id] = []
  bot.reply_to(message, "Alright, now forward the messages you'd like me to post.")

@bot.message_handler(commands=['post'], 
                      func=lambda m: (m.from_user.id , m.chat.id) in open_requests
                                      and m.forward_date is None)
def handle_post_step2(message):
  request_id = (message.from_user.id , message.chat.id)
  logging.info("Finishing up request from " + str(request_id))

  messages = sorted(open_requests[request_id], key=lambda m: m.date)
  output = "\n".join([m.forward_from.first_name + ": " + m.text for m in messages])
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
  del open_requests[request_id]


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

