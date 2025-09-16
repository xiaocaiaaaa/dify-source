from functools import wraps


class RedisWithPrefix:

    def __init__(self, client):
        self._client = client
        self._prefix = "caihu_"
        # self._prefix = os.getenv("REDIS_PREFIX", "") + "_"
        # 需要加前缀的 Redis 方法
        self._prefixed_methods = {"lock", "setex", "setnx", "get", "delete", "exists", "set", "expire", "hgetall", "hdel", "hlen", "hset", "incr", "ttl", "zremrangebyscore", "zcard", "zadd"}

    def _add_prefix(self, key):
        if isinstance(key, str) and not key.startswith(self._prefix):
            return self._prefix + key
        return key

    def _add_prefix_to_args(self, method_name, args):
        """
        自动对方法的第一个参数进行前缀处理
        """
        print(f"caihu method_name:{method_name},args:{args}")
        if method_name in self._prefixed_methods:
            # 默认对第一个 key 参数加前缀
            args = list(args)
            if args:
                args[0] = self._add_prefix(args[0])
            return tuple(args)
        else:
            return args

    def __getattr__(self, item):
        attr = getattr(self._client, item)

        if item in self._prefixed_methods and callable(attr):
            @wraps(attr)
            def wrapper(*args, **kwargs):
                args = self._add_prefix_to_args(item, args)
                return attr(*args, **kwargs)
            return wrapper
        else:
            return attr