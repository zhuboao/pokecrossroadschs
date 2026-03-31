Aide_EventScript_HaventCaughtEnough::
	msgbox Aide_Text_HaventCaughtEnoughMonsForItem
	release
	end

Aide_EventScript_NoRoomForItem::
	msgbox Aide_Text_DontHaveAnyRoomForItem
	release
	end

Aide_EventScript_DeclineCheckMons::
	msgbox Aide_Text_GetEnoughMonsComeBackForItem
	release
	end

Aide_Text_HaventCaughtEnoughMonsForItem::
	.string "让我查查……\n"
	.string "哎呀！你目前只捕捉了\l"
	.string "{STR_VAR_3}种宝可梦！\p"
	.string "想得到{STR_VAR_2}，\n"
	.string "需要捕捉{STR_VAR_1}种才行。$"

Aide_Text_GetEnoughMonsComeBackForItem::
	.string "……哦，我明白了。\p"
	.string "等你捕捉到{STR_VAR_1}种宝可梦后，\n"
	.string "再来拿{STR_VAR_2}吧。$"

Aide_Text_DontHaveAnyRoomForItem::
	.string "哦！你的背包\n"
	.string "已经没有空间放{STR_VAR_2}了。$"
