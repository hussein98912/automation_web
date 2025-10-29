import redis

url = "rediss://default:AVeyAAIncDIyMzc1YTkyOWFmNzI0ZTY0OWIyNTA3MTQ1NjFkZDg5NnAyMjI0NTA@welcome-quetzal-22450.upstash.io:6379"
r = redis.from_url(url, decode_responses=True)  # لا حاجة ssl=True

print(r.ping())  # يجب أن يطبع True
