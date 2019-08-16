import time, datetime

b = datetime.datetime.fromtimestamp(1565882379.6027274)
print(b)

a = time.localtime(1565882379.6027274)
print(a)
b = time.mktime(a)
print(b)