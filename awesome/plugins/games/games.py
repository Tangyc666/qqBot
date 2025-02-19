import asyncio
import datetime
import re
from random import randint, seed, choice
from time import time_ns

import china_idiom as idiom
import nonebot

from Services import poker_game, ru_game
from Services.util.ctx_utility import get_group_id, get_user_id, get_nickname
from awesome.Constants import user_permission as perm, group_permission
from awesome.Constants.function_key import HORSE_RACE, ROULETTE_GAME, POKER_GAME
from awesome.plugins.shadiao.shadiao import admin_group_control, setu_control
from qq_bot_core import user_control_module

get_privilege = lambda x, y: user_control_module.get_user_privilege(x, y)


class Storer:
    def __init__(self):
        self.stored_result = {}

    def set_store(self, function, ref, group_id: str, is_global: bool, user_id='-1'):
        if group_id not in self.stored_result:
            self.stored_result[group_id] = {}

        if function not in self.stored_result[group_id]:
            self.stored_result[group_id][function] = {}

        if is_global:
            self.stored_result[group_id][function] = ref
        else:
            self.stored_result[group_id][function][user_id] = ref

    def get_store(self, group_id, function, is_global: bool, user_id='-1', clear_after_use=True):
        if group_id not in self.stored_result:
            self.stored_result[group_id] = {}
            return ''

        if function not in self.stored_result[group_id]:
            self.stored_result[group_id][function] = ''
            return ''

        if is_global:
            temp = self.stored_result[group_id][function]
            if clear_after_use:
                self.stored_result[group_id][function] = ''
            return temp
        else:
            if user_id not in self.stored_result[group_id][function]:
                return ''

            info = self.stored_result[group_id][function][user_id]
            if clear_after_use:
                self.stored_result[group_id][function][user_id] = ''
            return info


class Horseracing:
    def __init__(self, user_guess: str):
        self.user_guess = user_guess
        self.winning_goal = 7
        self.actual_winner = -1
        self.adding_dict = {
            "正在勇往直前！": 6,
            "正在一飞冲天！": 4,
            "提起马蹄子就继续往前冲冲冲": 4,
            "如同你打日麻放铳一样勇往直前！": 4,
            "如同你打日麻放铳一样疾步迈进！": 3,
            "艰难的往前迈了几步": 2,
            "使用了忍术！它！飞！起！来！了！": 2,
            "艰难的往前迈了一小步": 1,
            "晃晃悠悠的往前走了一步": 1,
            "它窜稀的后坐力竟然让它飞了起来！": 3,
            "终于打起勇气，往前走了……一步": 1,
            "终于打起勇气，往前走了……两步": 2,
            "终于打起勇气，往前走了……三步": 3,
        }

        self.subtracting_dict = {
            "被地上的沥青的颜色吓傻了！止步不前": 0,
            '被電マplay啦！爽的倒退了2步！': -2,
            "打假赛往反方向跑了！": -3,
            "被旁边的选手干扰的吓得往后退了几步": -2,
            "哼啊啊啊啊啊~的叫了起来，落后大部队！": -2,
            "马晕厥了！可能是中暑了！这下要麻烦了！": -5,
            "它它它，居然！马猝死了！哎？等会儿！好像它马又复活了": -10,
            "吃多了在窜稀，暂时失去了战斗力": -1,
            "觉得敌不动我不动，敌动了……我还是不能动": 0,
            "觉得现在这个位置的空气不错，决定多待会儿~": 0,
            "突然站在原地深情的开始感叹——watashi mo +1": 0,
            "决定在原地玩会儿明日方舟": 0,
            "决定在原地玩会儿fgo": 0,
            "决定在原地玩会儿日麻": 0,
        }

        self.horse_list = [0, 0, 0, 0, 0, 0]
        self.response_list = []

    def if_play(self):
        try:
            temp = int(self.user_guess)
            if temp > len(self.horse_list):
                return False

        except ValueError:
            return False

        return True

    def if_win(self):
        for idx, elements in enumerate(self.horse_list):
            if elements >= self.winning_goal:
                self.actual_winner = str(idx + 1)
                return True

        return False

    def who_win(self):
        return self.actual_winner

    def get_play_result(self):
        self.response_list.clear()
        resp = ""
        i = 0
        for idx, elements in enumerate(self.horse_list):
            if randint(0, 5) >= 2:
                this_choice = choice(list(self.adding_dict))
                self.horse_list[idx] += self.adding_dict[this_choice]
                self.response_list.append(str(i + 1) + "号马, " + this_choice)

            else:
                this_choice = choice(list(self.subtracting_dict))
                self.horse_list[idx] += self.subtracting_dict[this_choice]
                self.response_list.append(str(i + 1) + "号马, " + this_choice)

            i += 1

        for elements in self.response_list:
            resp += elements + "\n"

        return resp

    def player_win(self):
        if self.actual_winner == self.user_guess:
            return True

        return False


BULLET_IN_GUN = 6
# 晚安模式在开启时会禁言中枪玩家6小时，而不是平常的2分钟。
ENABLE_GOOD_NIGHT_MODE = True

poker = poker_game.Pokergame()
GLOBAL_STORE = Storer()
game = ru_game.Russianroulette(BULLET_IN_GUN)


@nonebot.on_command('骰娘', only_to_me=False)
async def pao_tuan_shai_zi(session: nonebot.CommandSession):
    raw_message = session.current_arg
    if not re.fullmatch(r'^\d+[dD]\d+$', raw_message):
        await session.finish('用法错误：应为“xdy”, x 可以 = y，示例：1d100.')

    raw_message = raw_message.split()[0][1:].lower()
    args = raw_message.split('d')
    throw_times = int(args[0])
    if throw_times > 30:
        await session.finish('扔这么多干嘛，爬')

    max_val = int(args[1])
    result_list = [randint(1, max_val) for _ in range(throw_times)]
    result_sum = sum(result_list)

    await session.finish(
        f'筛子结果为：{", ".join([str(x) for x in result_list])}\n'
        f'筛子结果总和为：{result_sum}' if throw_times > 1 else ''
    )


@nonebot.on_command('赛马', only_to_me=False)
async def horse_race(session: nonebot.CommandSession):
    winner = session.get('winner', prompt='请输入一个胜方编号进行猜测（1-6）')
    race = Horseracing(winner)

    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    nickname = get_nickname(ctx)

    if race.if_play():
        while not race.if_win():
            await session.send(race.get_play_result())
            await asyncio.sleep(2)

        if race.player_win():
            await session.send("恭喜你猜赢啦！")
            if 'group_id' in ctx:
                setu_control.set_user_data(user_id, HORSE_RACE, user_nickname=nickname)

        else:
            await session.send(f"啊哦~猜输了呢！其实是{race.who_win()}号赢了哦")


@horse_race.args_parser
async def _(session: nonebot.CommandSession):
    stripped_arg = session.current_arg_text
    if session.is_first_run:
        if stripped_arg:
            session.state['winner'] = stripped_arg
        return

    if not stripped_arg:
        session.pause('请输入一个胜方编号进行猜测（1-6）')

    session.state[session.current_key] = stripped_arg


@nonebot.on_command('轮盘赌', only_to_me=False)
async def russian_roulette(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    id_num = get_group_id(ctx) if 'group_id' in ctx else get_user_id(ctx)
    user_id = get_user_id(ctx)

    if 'group_id' not in ctx:
        await session.finish('这是群组游戏！')

    if id_num not in game.game_dict:
        game.set_up_dict_by_group(id_num)

    if user_id not in game.game_dict[id_num]["playerDict"]:
        game.add_player_in(group_id=id_num, user_id=user_id)
    else:
        game.add_player_play_time(group_id=id_num, user_id=user_id)

    message_id = ctx['message_id']
    nickname = get_nickname(ctx)

    if not game.get_result(id_num):
        await session.send(f'[CQ:reply,id={message_id}]好像什么也没发生')
    else:
        death = game.get_death(id_num)
        death_dodge = randint(0, 100)
        if get_privilege(user_id, perm.OWNER) or death_dodge < 3:
            await session.finish(f'[CQ:reply,id={message_id}] sv_cheats 1 -> 成功触发免死\n'
                                 f'本应中枪几率为：%{1 / (game.get_bullet_in_gun() + 1 - death) * 100:.2f}')

        await session.send(
            f'[CQ:reply,id={message_id}]boom！你死了。这是第{death}枪，'
            f'理论几率为：{(1 / (game.get_bullet_in_gun() + 1 - death) * 100):.2f}%'
        )
        setu_control.set_user_data(user_id, ROULETTE_GAME, nickname)

        bot = nonebot.get_bot()
        if id_num == user_id:
            return

        rand_num = 60 * 2
        if 0 < datetime.datetime.now().hour < 4 and ENABLE_GOOD_NIGHT_MODE:
            rand_num = 60 * 60 * 6
            await session.send('晚安')

        await bot.set_group_ban(group_id=id_num, user_id=user_id, duration=rand_num)


@nonebot.on_command('转轮', only_to_me=False)
async def shuffle_gun(session: nonebot.CommandSession):
    seed(time_ns())
    ctx = session.ctx.copy()
    if 'group_id' not in ctx:
        await session.finish('这是群组游戏！')

    game.reset_gun(get_group_id(ctx))
    await session.send(f'{get_nickname(ctx)}转动了弹夹！流向改变了！')


@nonebot.on_command('设置子弹', only_to_me=False)
async def modify_gun_rounds(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)
    arg = session.current_arg
    if not arg:
        await session.finish('?')

    if not arg.isdigit() or int(arg) <= 0:
        await session.finish('必须是正整数')

    bullet = int(arg)

    if not get_privilege(user_id, perm.ADMIN) and (bullet <= 5 or bullet > 10):
        await session.finish('非主人只能设置5-10的区间哦')

    game.modify_bullets_in_gun(bullet)
    await session.finish('Done!')


@nonebot.on_command('成语接龙', only_to_me=False)
async def jielong(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_choice = session.current_arg_text
    random_idiom = GLOBAL_STORE.get_store(
        group_id=get_group_id(ctx),
        function='solitaire',
        is_global=True,
        user_id=str(get_user_id(ctx)),
        clear_after_use=False
    )

    first_play = not random_idiom

    if not random_idiom:
        random_idiom = get_random_idiom()

    GLOBAL_STORE.set_store(
        function='solitaire',
        ref=random_idiom,
        group_id=str(get_group_id(ctx)),
        is_global=True,
        user_id=str(get_user_id(ctx))
    )

    if first_play or not user_choice:
        user_choice = session.get('user_choice', prompt=f'请接龙：{random_idiom}')
        user_choice = re.sub(r'[!！]成语接龙\s+', '', str(user_choice).strip())
    if idiom.is_idiom_solitaire(random_idiom, user_choice):
        GLOBAL_STORE.set_store(
            function='solitaire',
            ref=user_choice,
            group_id=str(get_group_id(ctx)),
            is_global=True,
            user_id=str(get_user_id(ctx))
        )
        await session.finish(f'啧啧啧，什么嘛~还不错嘛~（好感度 +1）请继续~当前成语：{user_choice}')
    else:
        await session.finish(f'你接球呢ww （好感度 -1）现在的成语是{random_idiom}哦')


@nonebot.on_command('比大小', only_to_me=False)
async def the_poker_game(session: nonebot.CommandSession):
    ctx = session.ctx.copy()
    user_id = get_user_id(ctx)

    if 'group_id' in ctx:
        if admin_group_control.get_group_permission(get_group_id(ctx), group_permission.BANNED):
            await session.send('已设置禁止该群的娱乐功能。如果确认这是错误的话，请联系bot制作者')
            return

    else:
        await session.finish('抱歉哦这是群组游戏。')

    nickname = get_nickname(ctx)

    if get_privilege(user_id, perm.OWNER):
        drawed_card, time_seed = poker.get_random_card(user_id, str(get_group_id(ctx)), rigged=10)
    else:
        drawed_card, time_seed = poker.get_random_card(user_id, str(get_group_id(ctx)))

    stat, response = poker.compare_two(str(get_group_id(ctx)))

    if not stat and response == -1:
        GLOBAL_STORE.set_store(
            'guess',
            drawed_card,
            get_group_id(ctx),
            is_global=True
        )
        await session.send(f"玩家[CQ:at,qq={user_id}]拿到了加密过的卡：{encrypt_card(drawed_card, time_seed)}\n"
                           f"有来挑战一下的么？\n"
                           f"本次游戏随机种子：{time_seed}")

    else:
        player_one_card = GLOBAL_STORE.get_store(
            get_group_id(ctx),
            'guess',
            is_global=True
        )
        if not stat and response == -2:
            await session.send(f"玩家[CQ:at,qq={user_id}]抓到了{drawed_card}。咳咳虽然斗争很激烈，但是平局啦！！")
        else:
            await session.send(f"玩家[CQ:at,qq={user_id}]抓到了{drawed_card}\n"
                               f"玩家1的加密卡为："
                               f"{player_one_card}。\n"
                               f"玩家[CQ:at,qq={response}]获胜！")

            setu_control.set_user_data(response, POKER_GAME, nickname)

        poker.clear_result(str(get_group_id(ctx)))


def encrypt_card(card, time_seed):
    result = ''
    for idx, char in enumerate(card):
        order = (ord(char) ^ ord(time_seed[-idx - 6]))
        result += chr(order % 32 + 100)

    return result


def get_random_idiom() -> str:
    with open('data/util/idiom.csv', 'r', encoding='utf-8') as file:
        content = file.readlines()

    # Remove first line in csv file.
    content = [x.strip() for x in content][1:]
    random_idiom = choice(content).split(',')[6]
    while not idiom.is_idiom(random_idiom):
        random_idiom = choice(content).split(',')[6]

    return random_idiom
