Route2_Frlg_MapScripts::
	.byte 0

Route2_EventScript_RouteSign::
	msgbox Route2_Text_RouteSign, MSGBOX_SIGN
	end

Route2_EventScript_DiglettsCaveSign::
	msgbox Route2_Text_DiglettsCave, MSGBOX_SIGN
	end

Route2_Text_RouteSign::
	.string "2号道路\n"
	.string "常青市-深灰市$"

Route2_Text_DiglettsCave::
	.string "地鼠洞穴$"

Route2_EventScript_ProfBirchAssistant::
	lock
	faceplayer
	checkflag FLAG_GOT_FLIGHT_CALL
	goto_if TRUE, Route2_EventScript_ProfBirchAssistant_Done

	msgbox Route2_Text_Hoenn, MSGBOX_DEFAULT
	giveitem ITEM_FLIGHT_CALL, 1
	setflag FLAG_VISITED_LITTLEROOT_TOWN
	setflag FLAG_GOT_FLIGHT_CALL
	msgbox Route2_Text_ReceivedDevice, MSGBOX_DEFAULT
	msgbox Route2_Text_HoennAfterGift, MSGBOX_DEFAULT
	closemessage
	applymovement ProfBirchAssistant, Route2_Movement_ProfBirchAssistantWarpOut
	waitmovement 0
	setflag FLAG_HIDE_ROUTE_PROF_ASSISTANT
	hideobjectat ProfBirchAssistant, MAP_ROUTE2
	releaseall
	end

Route2_EventScript_ProfBirchAssistant_Done::
	releaseall
	end

Route2_Text_Hoenn:
	.string "{PLAYER}！！！\n大木博士说你会\l经过这里的。\p小田卷博士在丰缘，\n托我来找你。\p他想把这个给你。$"

Route2_Text_ReceivedDevice:
	.string "{PLAYER}获得了\n飞行呼叫！$"

Route2_Text_HoennAfterGift:
	.string "有了那个道具，\n就可以前往丰缘了。\p我也该回研究所了，\n再见！$"

Route2_Movement_ProfBirchAssistantWarpOut:
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	set_invisible
	step_end
