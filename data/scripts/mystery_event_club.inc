.equ GAVE_PROFILE,  VAR_TEMP_1

MysteryEventClub_EventScript_Woman::
	lock
	faceplayer
	goto_if_eq GAVE_PROFILE, TRUE, EventScript_AlreadyGaveProfile
	goto_if_set FLAG_SYS_SET_TRAINER_CARD_PROFILE, EventScript_GivenProfileBefore
	msgbox Text_IdLoveToHearYourProfile
	goto EventScript_AskForProfile
	end

EventScript_AlreadyGaveProfile:
	msgbox Text_TellMoreNextTime
	release
	end

EventScript_AskForProfile:
	message Text_TellMeWhatsYourProfile
	waitmessage
	multichoice 18, 6, MULTI_YESNOINFO_2, FALSE
	switch VAR_RESULT
	case 0, EventScript_AcceptGiveProfile
	case 1, EventScript_DeclineGiveProfile
	case 2, EventScript_ProfileInfo
	case MULTI_B_PRESSED, EventScript_DeclineGiveProfile
	end

EventScript_ProfileInfo:
	msgbox Text_ExplainProfile
	goto EventScript_AskForProfile
	end

EventScript_AcceptGiveProfile:
	msgbox Text_WhatsYourProfile
	closemessage
	goto EventScript_GiveProfile
	end

EventScript_CancelGiveProfile:
	msgbox Text_DecidedNotTo
	release
	end

EventScript_GaveProfile:
	setvar GAVE_PROFILE, TRUE
	setvar VAR_0x8004, 0
	special ShowEasyChatProfile
	waitmessage
	delay 80
	msgbox Text_ProfileSaysSomethingAboutYou
	release
	end

EventScript_DeclineGiveProfile:
	msgbox Text_DontBeLikeThat
	release
	end

EventScript_GivenProfileBefore:
	msgbox Text_HiWeMeetAgain
	goto EventScript_AskForNewProfile
	end

EventScript_AskForNewProfile:
	message Text_ChangeYourProfile
	waitmessage
	multichoice 18, 6, MULTI_YESNOINFO_2, FALSE
	switch VAR_RESULT
	case 0, EventScript_AcceptGiveNewProfile
	case 1, EventScript_DeclineGiveNewProfile
	case 2, EventScript_ProfileInfo2
	@case MULTI_B_PRESSED, EventScript_DeclineGiveNewProfile
	end

EventScript_ProfileInfo2:
	msgbox Text_ExplainProfile
	goto EventScript_AskForNewProfile
	end

EventScript_AcceptGiveNewProfile:
	msgbox Text_WhatAreYouLikeNow
	closemessage
	goto EventScript_GiveProfile
	end

EventScript_DeclineGiveNewProfile:
	msgbox Text_LikeProfileWayItIs
	release
	end

EventScript_GaveSpecialProfile:
	setvar GAVE_PROFILE, TRUE
	setvar VAR_0x8004, 0
	special ShowEasyChatProfile
	waitmessage
	delay 80
	msgbox Text_HeardThatBefore
	release
	end

EventScript_GiveProfile:
	setvar VAR_0x8004, EASY_CHAT_TYPE_PROFILE
	call Common_ShowEasyChatScreen
	lock
	faceplayer
	goto_if_eq VAR_0x8004, 0, EventScript_GaveSpecialProfile
	goto_if_eq VAR_RESULT, FALSE, EventScript_CancelGiveProfile
	goto_if_eq VAR_RESULT, TRUE, EventScript_GaveProfile
	end

Text_IdLoveToHearYourProfile:
	.string "嗨，很高兴认识你！\p"
	.string "……你好像不太友善呢。\n"
	.string "能跟我打个招呼吗？\p"
	.string "来嘛，告诉我一些\n"
	.string "关于你自己的事吧。\p"
	.string "我很想听你的档案介绍！$"

Text_TellMeWhatsYourProfile:
	.string "说说你自己的优点吧。\n"
	.string "你的档案是什么？$"

Text_ExplainProfile:
	.string "档案是用四个\n"
	.string "词或短语写成的。\p"
	.string "有很多词可以供你\n"
	.string "选择来填写档案。\p"
	.string "这些词分成了\n"
	.string "几个方便的组别。\p"
	.string "先选一个组别，\n"
	.string "再选一个词或短语。\p"
	.string "……比听起来简单多了。\n"
	.string "要不要试试看？$"

Text_WhatsYourProfile:
	.string "你的档案是什么？$"

Text_DontBeLikeThat:
	.string "哎……别这样嘛。\n"
	.string "你可以告诉我你的档案的。$"

Text_DecidedNotTo:
	.string "哦，你决定不说了？\n"
	.string "你真是善变呢。$"

Text_HiWeMeetAgain:
	.string "嗨！\n"
	.string "我们又见面了！$"

Text_ChangeYourProfile:
	.string "你想更改\n"
	.string "你的档案吗？$"

Text_WhatAreYouLikeNow:
	.string "你现在怎么样？\n"
	.string "我很想知道。$"

Text_LikeProfileWayItIs:
	.string "好的，你喜欢\n"
	.string "现在的档案。\p"
	.string "我也觉得很好。$"

Text_ProfileSaysSomethingAboutYou:
	.string "嗯嗯……\p"
	.string "你的档案真的能体现出\n"
	.string "你是什么样的人。\p"
	.string "更了解你之后，\n"
	.string "我们之间的友谊更深了！$"

Text_HeardThatBefore:
	.string "哦，我以前听过这句话……\p"
	.string "我那住在远方的表亲，\n"
	.string "好像经常这么说。$"

Text_TellMoreNextTime:
	.string "下次请多告诉我一些\n"
	.string "关于你自己的事！$"
