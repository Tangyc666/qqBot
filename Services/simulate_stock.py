import copy
from datetime import datetime
from json import dump, loads
from os import getcwd
from os.path import exists
from typing import Union

from Services.stock import Stock


class SimulateStock:
    def __init__(self):
        self.STOCK_NOT_EXISTS = '未开盘或股票不存在（如果不确定股票代码，请使用！股票 名称来找一下~）'
        self.NO_INFO = '您啥还没买呢哦~'

        self.file_name = f'{getcwd()}/Services/util/userStockRecord.json'
        self.stock_price_cache = {}
        self.user_stock_data = {"data": {}}
        if not exists(self.file_name):
            self._store_user_data()

        self.user_stock_data = self._read_user_stock_data()

    def _read_user_stock_data(self) -> dict:
        with open(self.file_name, encoding='utf-8') as file:
            return loads(file.read())

    def _store_user_data(self):
        with open(self.file_name, 'w+', encoding='utf-8') as file:
            dump(self.user_stock_data, file, indent=4, ensure_ascii=False)

    async def get_all_stonk_log_by_user(self, uid: Union[int, str], ctx=None):
        uid = str(uid)
        try:
            stonk_whole_log = self.user_stock_data['data'][uid]
        except KeyError:
            return self.NO_INFO

        if not stonk_whole_log:
            return self.NO_INFO

        response = [await self.my_money_spent_by_stock_code(uid, stock_code) for stock_code in stonk_whole_log]
        time_awareness = ''
        if datetime.now().hour == 12:
            time_awareness = '【午间休市】\n'
        elif datetime.now().hour == 11 and datetime.now().minute >= 30:
            time_awareness = '【午间休市】\n'
        elif datetime.now().hour > 15 or (datetime.now().hour <= 9 and datetime.now().minute <= 30):
            time_awareness = '【休市】\n'
        elif datetime.now().hour == 9 and 15 <= datetime.now().minute <= 25:
            time_awareness = '【集合竞价·开盘】\n'
        elif datetime.now().hour == 14 and datetime.now().minute >= 57:
            time_awareness = '【集合竞价·收盘】\n'

        # backfill
        self._backfill_nickname(uid, ctx)
        return f'{time_awareness}' + '\n'.join(response)

    def _backfill_nickname(self, uid: Union[str, int], ctx=None):
        if ctx is not None:
            try:
                self.user_stock_data['data'][uid]['nickname'] = ctx['sender']['nickname']
            except KeyError:
                pass

            self._store_user_data()

    async def get_all_user_info(self):
        user_data = copy.deepcopy(self.user_stock_data)
        data = user_data['data']
        response = ''
        user_data_info = []
        for uid in data:
            data = await self._get_user_overall_stat(uid)
            user_data_info.append(data)

        if len(user_data_info) > 3:
            sorted_list_reverse = sorted(user_data_info, key=lambda d: d["ratio"], reverse=True)
            sorted_list = sorted_list_reverse[::-1][:3]
            sorted_list_reverse = sorted_list_reverse[:3]
        else:
            sorted_list_reverse = sorted(user_data_info, key=lambda d: d["ratio"], reverse=True)
            sorted_list = sorted_list_reverse[::-1]

        response += f'龙虎榜：\n\n'
        for idx, data in enumerate(sorted_list_reverse):
            response += f'收益第{idx + 1}: {data["nickname"]}\n' \
                        f'【总资产{data["total"]:.2f}软妹币' \
                        f'（总收益率：{data["ratio"]:.2f}% {"↑" if data["ratio"] > 0 else "↓"}）】\n'

        response += f'\n韭菜榜：\n\n'
        for idx, data in enumerate(sorted_list):
            response += f'收益倒数第{idx + 1}: {data["nickname"]}\n' \
                        f'【总资产{data["total"]:.2f}软妹币' \
                        f'（总收益率：{data["ratio"]:.2f}% {"↑" if data["ratio"] > 0 else "↓"}）】\n'
        self.stock_price_cache.clear()
        return response.strip()

    async def sell_stock(self, uid: Union[int, str], stock_code: str, amount: str, ctx=None):
        if not amount.isdigit():
            return f'卖不了{amount}股'
        uid = str(uid)
        amount = int(amount)

        if amount < 100 or amount % 100 != 0:
            return '购买数量必须为大于100且为100倍数的正整数'

        try:
            data = self.user_stock_data['data'][uid][stock_code]
            purchase_count = data['purchaseCount']
            if purchase_count < amount:
                return '您没那么多股票谢谢'

            stock = Stock(stock_code)
            price_now, stock_name = await stock.get_purchase_price()
            if price_now <= 0:
                return self.STOCK_NOT_EXISTS

            self.user_stock_data['data'][uid][stock_code]['purchaseCount'] -= amount

            price_earned = price_now * amount
            self.user_stock_data['data'][uid]['totalMoney'] += price_earned
            if self.user_stock_data['data'][uid][stock_code]['purchaseCount'] == 0:
                del self.user_stock_data['data'][uid][stock_code]
            else:
                self.user_stock_data['data'][uid][stock_code]['moneySpent'] -= price_earned
                self.user_stock_data['data'][uid][stock_code]['purchasePrice'] = \
                    self.user_stock_data['data'][uid][stock_code]['moneySpent'] / \
                    self.user_stock_data['data'][uid][stock_code]['purchaseCount']

            self._backfill_nickname(uid, ctx)
            self._store_user_data()
            return f'您已每股{price_now}软妹币的价格卖出了{amount}股{stock_name}，' \
                   f'现在您有{self.user_stock_data["data"][uid]["totalMoney"]:.2f}软妹币了~'

        except KeyError:
            return self.NO_INFO

    async def _get_user_overall_stat(self, uid: Union[int, str]) -> dict:
        data = self.user_stock_data['data']
        uid = str(uid)
        try:
            total_money = data[uid]['totalMoney']
            if 'nickname' in data[uid]:
                nickname = data[uid]['nickname']
            else:
                nickname = '匿名'

            current_stock_money = 0
            for stock in data[uid]:
                if not isinstance(data[uid][stock], dict):
                    continue

                if stock not in self.stock_price_cache:
                    stock_entity = Stock(stock)
                    price_now, _ = await stock_entity.get_purchase_price()
                    self.stock_price_cache[stock] = price_now
                else:
                    price_now = self.stock_price_cache[stock]

                current_stock_money += price_now * data[uid][stock]['purchaseCount']

            total_money += current_stock_money
            ratio = ((total_money - (10 ** 6 * 5)) / (10 ** 6 * 5)) * 100

            return {
                "total": total_money,
                "ratio": ratio,
                "nickname": nickname
            }

        except KeyError:
            return {}

    async def my_money_spent_by_stock_code(self, uid: Union[int, str], stock_code: str) -> (str, float, float):
        uid = str(uid)
        if not stock_code.isdigit():
            return ''

        try:
            stock_to_check = self.user_stock_data['data'][uid][stock_code]
        except KeyError:
            return self.NO_INFO

        total_count = stock_to_check['purchaseCount']
        if total_count == 0:
            return ''

        total_money_spent = stock_to_check['moneySpent']
        avg_money = stock_to_check['purchasePrice']

        stock = Stock(stock_code)
        price_now, stock_name = await stock.get_purchase_price()
        if price_now <= 0:
            return self.STOCK_NOT_EXISTS

        new_price = price_now * total_count
        rate = (new_price - total_money_spent) / total_money_spent * 100

        return f'{stock_name}[{stock_code}] x {total_count} -> 成本{total_money_spent:.2f}软妹币\n' \
               f'（最新市值：{new_price:.2f}软妹币 | ' \
               f'持仓盈亏：{rate:.2f}% {"↑" if rate > 0 else "↓"} | 平摊成本：{avg_money:.2f}软妹币/股）\n'

    async def buy_with_code_and_amount(
            self, uid: Union[int, str], stock_code: str, amount: Union[str, int], ctx=None
    ) -> str:
        if isinstance(amount, str):
            if not amount.isdigit():
                return '购买数量不合法'

            amount = int(amount)
            if amount < 100 or amount % 100 != 0:
                return '购买数量必须为大于100且为100倍数的正整数'

        if not stock_code.isdigit():
            return '为了最小化bot的响应时间，请使用股票的数字代码购买~'

        data = self.user_stock_data['data']
        uid = str(uid)
        if uid not in data:
            # 初始资金100万应该够了吧？
            self.user_stock_data['data'][uid] = {"totalMoney": 10 ** 6 * 5}

        stock = Stock(stock_code)
        price_now, stock_name = await stock.get_purchase_price()
        if price_now <= 0:
            return self.STOCK_NOT_EXISTS

        if stock_code not in data[uid]:
            self.user_stock_data['data'][uid][stock_code] = {
                "purchasePrice": 0,
                "purchaseCount": 0,
                "moneySpent": 0
            }

        need_money = amount * price_now
        user_money = self.user_stock_data['data'][uid]['totalMoney']
        if need_money > user_money:
            return '您没钱了'

        self._backfill_nickname(uid, ctx)

        self.user_stock_data['data'][uid]['totalMoney'] = user_money - need_money

        self.user_stock_data['data'][uid][stock_code]["purchaseCount"] += amount
        self.user_stock_data['data'][uid][stock_code]["moneySpent"] += need_money
        self.user_stock_data['data'][uid][stock_code]["purchasePrice"] = round(
            self.user_stock_data['data'][uid][stock_code]["moneySpent"] /
            self.user_stock_data['data'][uid][stock_code]["purchaseCount"],
            2
        )

        self._store_user_data()
        return f'您花费了{need_money:.2f}软妹币已每股{price_now:.2f}软妹币的价格购买了{amount}股{stock_name}股票'
