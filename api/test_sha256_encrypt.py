import hashlib


class TestSHA256:

    def sha256_encrypt(self, input_string: str) -> str:
        """SHA256 加密方法（与待测试代码一致）"""
        input_bytes = input_string.encode('utf-8')
        sha256_hash = hashlib.sha256()
        sha256_hash.update(input_bytes)
        return sha256_hash.hexdigest()

    def test_encryption(self):
        """测试加密逻辑"""
        # 模拟输入参数
        timeStamp = "1688011678224"  # 示例时间戳（可替换为动态生成的当前时间）
        secret_key = "abc"

        # 生成待加密字符串
        input_string = secret_key + timeStamp
        print(f"Input string: {input_string}")

        expected_hash = "77fc1623c2e0ff3d03ceb44d3f66a1d9f266efad22e93bc8e4582033eb6ec1d0"
        print(f"expected_hash result: {expected_hash}")

        # 模拟实际调用（假设这是待测试的代码片段）
        actual_hash = self.sha256_encrypt(input_string)
        print(f"actual result: {actual_hash}")


if __name__ == "__main__":
    tester = TestSHA256()
    tester.test_encryption()