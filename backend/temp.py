from kiwoom_python.api import KiwoomAPI
import os
api = KiwoomAPI()

# 전체 속성 보기
print(dir(api))

# 'code'가 들어가는 메서드만 필터링
print([name for name in dir(api) if 'code' in name.lower()])
print([name for name in dir(api) if 'market' in name.lower()])