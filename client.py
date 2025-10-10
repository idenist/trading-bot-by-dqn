from pykiwoom.kiwoom import Kiwoom
import time

class SuccessfulTradingCode:
    def __init__(self):
        
        self.kiwoom = Kiwoom()
        self.kiwoom.CommConnect(block=True)
        
        self.account = "8111496111"  # 5억원 계좌 (실제 체결됨)
        
    def get_samsung_info(self):
        """삼성전자 현재가"""
        try:
            df = self.kiwoom.block_request("opt10001",
                                         종목코드="005930",
                                         output="주식기본정보",
                                         next=0)
            
            if len(df) > 0:
                current_price = abs(int(df['현재가'][0]))
                print(f"삼성전자 현재가: {current_price:,}원")
                return current_price
            return 0
        except:
            return 0
    
    def check_samsung_holding(self):
        """삼성전자 보유량 확인"""
        try:
            df = self.kiwoom.block_request("opw00018",
                                         계좌번호=self.account,
                                         비밀번호="",
                                         비밀번호입력매체구분="00",
                                         조회구분=2,
                                         output="계좌평가잔고개별합산",
                                         next=0)
            
            for i in range(len(df)):
                try:
                    종목번호 = str(df.iloc[i]['종목번호']).strip()
                    if 종목번호 == "005930":
                        보유수량 = int(float(str(df.iloc[i]['보유수량']).strip()))
                        매입가 = int(float(str(df.iloc[i]['매입가']).strip())) if df.iloc[i]['매입가'] else 0
                        평가손익 = int(float(str(df.iloc[i]['평가손익']).strip())) if df.iloc[i]['평가손익'] else 0
                        
                        print(f"삼성전자 보유: {보유수량}주")
                        print(f"매입가: {매입가:,}원")
                        print(f"평가손익: {평가손익:+,}원")
                        
                        return 보유수량
                except:
                    continue
            
            print("삼성전자 보유 없음")
            return 0
        except:
            return 0
    
    def execute_samsung_order(self, action, quantity):
        """삼성전자 주문 (실제 체결됨)"""
        order_name = "매수" if action == 1 else "매도"
        
        print(f"\n삼성전자 {order_name} 주문!")
        print(f"계좌: {self.account}")
        print(f"수량: {quantity}주")
        
        try:
            result = self.kiwoom.SendOrder(
                f"삼성{order_name}",
                "0101",
                self.account,
                action,
                "005930",
                quantity,
                0,
                "03",
                ""
            )
            
            print(f"주문 결과: {result}")
            
            if result == 0:
                print(f"{order_name} 주문 성공!")
                return True
            else:
                print(f"{order_name} 주문 실패")
                return False
        except:
            return False
    
    def check_order_execution(self):
        """체결 확인"""
        try:
            # 미체결 주문 확인
            df = self.kiwoom.block_request("opt10075",
                                         계좌번호=self.account,
                                         전체종목구분=0,
                                         매매구분=0,
                                         종목코드="005930",
                                         체결구분=0,
                                         거래소구분=0,
                                         output="미체결",
                                         next=0)
            
            if len(df) > 0:
                for i in range(len(df)):
                    try:
                        종목명 = str(df.iloc[i]['종목명']).strip()
                        주문상태 = str(df.iloc[i]['주문상태']).strip()
                        체결량 = str(df.iloc[i]['체결량']).strip()
                        
                        if '삼성' in 종목명:
                            print(f"삼성전자 주문상태: {주문상태}")
                            print(f"체결량: {체결량}주")
                            
                            if int(체결량) > 0:
                                print("체결 확인!")
                                return True
                    except:
                        continue
            
            return False
        except:
            return False
    
    def run_successful_trade(self):
        """성공한 거래 패턴 실행"""
        print("=" * 50)
        print("실제 체결 성공한 거래 패턴")
        print("=" * 50)
        
        # 1. 현재가 확인
        price = self.get_samsung_info()
        if price == 0:
            return False
        
        # 2. 보유량 확인
        holding = self.check_samsung_holding()
        
        # 3. 거래 실행
        if holding == 0:
            print("\n보유 없음 → 매수")
            success = self.execute_samsung_order(1, 10)
        else:
            print(f"\n{holding}주 보유 → 매도")
            success = self.execute_samsung_order(2, holding)
        
        if success:
            print("\n체결 확인 (10초 대기)...")
            time.sleep(10)
            
            # 체결 확인
            executed = self.check_order_execution()
            if executed:
                print("거래 체결 완료!")
                
                # 최종 보유량 확인
                final_holding = self.check_samsung_holding()
                return True
        
        return False

def main():
    try:
        print("실제 체결 성공한 거래 코드")
        print("이전에 삼성전자 10주 체결 성공")
        print("=" * 40)
        
        trader = SuccessfulTradingCode()
        result = trader.run_successful_trade()
        
        if result:
            print("\n거래 성공!")
        else:
            print("\n거래 대기 중")
        
    except Exception as e:
        print(f"오류: {e}")
    
    input("Enter로 종료...")

if __name__ == "__main__":
    main()
