from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Literal

import ambr
import enka
import hakushin
from discord import File
from genshin.models import ZZZFullAgent

from hoyo_buddy.draw import funcs
from hoyo_buddy.models import (
    AgentNameData,
    DoubleBlock,
    HoyolabGICharacter,
    HoyolabHSRCharacter,
    SingleBlock,
    UnownedGICharacter,
    UnownedHSRCharacter,
    UnownedZZZCharacter,
    ZZZDrawData,
)

from .static import download_images

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO

    import genshin
    from genshin.models import (
        FullBattlesuit,
        ImgTheaterData,
        PartialGenshinUserStats,
        SpiralAbyss,
        StarRailAPCShadow,
        StarRailChallenge,
        StarRailChallengeSeason,
        StarRailNote,
        StarRailPureFiction,
        ZZZNotes,
    )

    from hoyo_buddy.models import DrawInput, FarmData, ItemWithDescription, ItemWithTrailing, Reward


async def draw_item_list_card(
    draw_input: DrawInput, items: list[ItemWithDescription] | list[ItemWithTrailing]
) -> File:
    await download_images(
        [item.icon for item in items if item.icon is not None], "item-list", draw_input.session
    )
    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.draw_item_list,
        items,
        draw_input.dark_mode,
        draw_input.locale.value,
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_checkin_card(draw_input: DrawInput, rewards: list[Reward]) -> BytesIO:
    await download_images([r.icon for r in rewards], "check-in", draw_input.session)
    return await draw_input.loop.run_in_executor(
        draw_input.executor, funcs.draw_checkin_card, rewards, draw_input.dark_mode
    )


async def draw_hsr_build_card(
    draw_input: DrawInput,
    character: enka.hsr.Character | HoyolabHSRCharacter,
    image_url: str,
    primary_hex: str,
) -> BytesIO:
    urls: list[str] = []
    urls.append(image_url)
    urls.extend(trace.icon for trace in character.traces)

    stats = (
        character.stats if isinstance(character, HoyolabHSRCharacter) else character.stats.values()
    )
    urls.extend(stat.icon for stat in stats)

    for relic in character.relics:
        urls.extend((relic.icon, relic.main_stat.icon))
        urls.extend(sub_stat.icon for sub_stat in relic.sub_stats)

    if character.light_cone is not None:
        urls.append(character.light_cone.icon.image)
        if isinstance(character, enka.hsr.Character):
            urls.extend(stat.icon for stat in character.light_cone.stats)

    await download_images(urls, "hsr-build-card", draw_input.session)

    return await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.hsr.draw_hsr_build_card,
        character,
        draw_input.locale.value,
        draw_input.dark_mode,
        image_url,
        primary_hex,
    )


async def draw_hsr_notes_card(draw_input: DrawInput, notes: StarRailNote) -> BytesIO:
    await download_images(
        [exped.item_url for exped in notes.expeditions],
        folder="hsr-notes",
        session=draw_input.session,
    )
    return await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.hsr.draw_hsr_notes_card,
        notes,
        draw_input.locale.value,
        draw_input.dark_mode,
    )


async def draw_gi_build_card(
    draw_input: DrawInput,
    character: enka.gi.Character | HoyolabGICharacter,
    *,
    image_url: str,
    zoom: float,
    template: Literal[1, 2],
    top_crop: bool,
    rank: str | None,
) -> BytesIO:
    urls: list[str] = [image_url, character.weapon.icon, character.icon.gacha]
    urls.extend(artifact.icon for artifact in character.artifacts)
    urls.extend(talent.icon for talent in character.talents)
    urls.extend(const.icon for const in character.constellations)

    if template == 2:
        async with ambr.AmbrAPI() as api:
            characters = await api.fetch_characters()
            ambr_char = next((char for char in characters if str(character.id) in char.id), None)
            if ambr_char is None:
                msg = f"Character {character.id} not found in Amber's database."
                raise ValueError(msg)

        await download_images(urls, "gi-build-card2", draw_input.session)
        card = funcs.genshin.GITempTwoBuildCard(
            locale=draw_input.locale.value,
            character=character,
            zoom=zoom,
            dark_mode=draw_input.dark_mode,
            character_image=image_url,
            english_name=ambr_char.name,
            top_crop=top_crop,
            rank=rank,
        )
        buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)
    else:
        await download_images(urls, "gi-build-card", draw_input.session)
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.genshin.draw_genshin_card,
            draw_input.locale.value,
            draw_input.dark_mode,
            character,
            image_url,
            zoom,
            rank,
        )
    return buffer


async def draw_gi_notes_card(draw_input: DrawInput, notes: genshin.models.Notes) -> BytesIO:
    await download_images(
        [exped.character_icon for exped in notes.expeditions],
        folder="gi-notes",
        session=draw_input.session,
    )
    return await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.genshin.draw_genshin_notes_card,
        notes,
        draw_input.locale.value,
        draw_input.dark_mode,
    )


async def draw_farm_card(draw_input: DrawInput, farm_data: list[FarmData]) -> File:
    image_urls = (
        [r.icon for data in farm_data for r in data.domain.rewards]
        + [c.icon for data in farm_data for c in data.characters]
        + [w.icon for data in farm_data for w in data.weapons]
    )
    await download_images(image_urls, folder="farm", session=draw_input.session)
    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.draw_farm_card,
        farm_data,
        draw_input.locale.value,
        draw_input.dark_mode,
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_gi_characters_card(
    draw_input: DrawInput,
    characters: Sequence[genshin.models.GenshinDetailCharacter | UnownedGICharacter],
    pc_icons: dict[str, str],
    talent_orders: dict[int, list[int]],
) -> File:
    urls: list[str] = []
    for c in characters:
        if isinstance(c, UnownedGICharacter):
            continue
        urls.append(c.weapon.icon)
    urls.extend(pc_icons[str(c.id)] for c in characters if str(c.id) in pc_icons)

    await download_images(urls, "gi-characters", draw_input.session)
    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.genshin.draw_character_card,
        characters,
        pc_icons,
        talent_orders,
        draw_input.dark_mode,
        draw_input.locale.value,
    )
    buffer.seek(0)

    return File(buffer, filename=draw_input.filename)


async def draw_hsr_characters_card(
    draw_input: DrawInput,
    characters: Sequence[genshin.models.StarRailDetailCharacter | UnownedHSRCharacter],
    pc_icons: dict[str, str],
) -> File:
    urls: list[str] = []
    for c in characters:
        if isinstance(c, UnownedHSRCharacter) or c.equip is None:
            continue
        urls.append(c.equip.icon)
    urls.extend(pc_icons[str(c.id)] for c in characters if str(c.id) in pc_icons)

    await download_images(urls, "hsr-characters", draw_input.session)
    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.hsr.draw_character_card,
        characters,
        pc_icons,
        draw_input.dark_mode,
        draw_input.locale.value,
    )
    buffer.seek(0)

    return File(buffer, filename=draw_input.filename)


async def draw_spiral_abyss_card(
    draw_input: DrawInput, abyss: SpiralAbyss, characters: Sequence[genshin.models.Character]
) -> File:
    async with ambr.AmbrAPI() as api:
        character_icons = {
            character.id.split("-")[0]: character.icon for character in await api.fetch_characters()
        }

    character_ranks = {char.id: char.constellation for char in characters}
    urls = [
        character_icons[str(chara.id)]
        for floor in abyss.floors
        for chamber in floor.chambers
        for battle in chamber.battles
        for chara in battle.characters
    ]
    with contextlib.suppress(IndexError):
        urls.extend(
            character_icons[str(chara.id)]
            for chara in (
                abyss.ranks.most_bursts_used[0],
                abyss.ranks.most_damage_taken[0],
                abyss.ranks.most_kills[0],
                abyss.ranks.most_skills_used[0],
                abyss.ranks.strongest_strike[0],
            )
        )
    await download_images(urls, "abyss", draw_input.session)

    card = funcs.genshin.SpiralAbyssCard(
        abyss,
        locale=draw_input.locale.value,
        character_icons=character_icons,
        character_ranks=character_ranks,
    )
    buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_exploration_card(draw_input: DrawInput, user: PartialGenshinUserStats) -> File:
    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.genshin.ExplorationCard(user, draw_input.dark_mode, draw_input.locale.value).draw,
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_moc_card(
    draw_input: DrawInput, data: StarRailChallenge, season: StarRailChallengeSeason
) -> File:
    for floor in data.floors:
        icons = [chara.icon for chara in floor.node_1.avatars + floor.node_2.avatars]
        await download_images(icons, "moc", draw_input.session)

    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor, funcs.hsr.moc.MOCCard(data, season, draw_input.locale.value).draw
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_pure_fiction_card(
    draw_input: DrawInput, data: StarRailPureFiction, season: StarRailChallengeSeason
) -> File:
    for floor in data.floors:
        icons = [chara.icon for chara in floor.node_1.avatars + floor.node_2.avatars]
        await download_images(icons, "pf", draw_input.session)

    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.hsr.pure_fiction.PureFictionCard(data, season, draw_input.locale.value).draw,
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_apc_shadow_card(
    draw_input: DrawInput, data: StarRailAPCShadow, season: StarRailChallengeSeason
) -> File:
    for floor in data.floors:
        icons = [chara.icon for chara in floor.node_1.avatars + floor.node_2.avatars]
        await download_images(icons, "apc-shadow", draw_input.session)

    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.hsr.apc_shadow.APCShadowCard(data, season, draw_input.locale.value).draw,
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_img_theater_card(
    draw_input: DrawInput, data: ImgTheaterData, chara_consts: dict[int, int]
) -> File:
    async with ambr.AmbrAPI() as api:
        character_icons = {
            character.id.split("-")[0]: character.icon for character in await api.fetch_characters()
        }

    icons: list[str] = []

    if hasattr(data, "battle_stats") and data.battle_stats is not None:
        characters = (
            data.battle_stats.max_damage_character,
            data.battle_stats.max_defeat_character,
            data.battle_stats.max_take_damage_character,
        )
        icons.extend(character_icons[str(chara.id)] for chara in characters if chara is not None)

    for act in data.acts:
        icons.extend(character_icons[str(chara.id)] for chara in act.characters)

    await download_images(icons, "img-theater", draw_input.session)

    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.genshin.ImgTheaterCard(
            data, chara_consts, character_icons, draw_input.locale.value
        ).draw,
    )

    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_zzz_notes_card(draw_input: DrawInput, notes: ZZZNotes) -> BytesIO:
    return await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.zzz.draw_zzz_notes,
        notes,
        draw_input.locale.value,
        draw_input.dark_mode,
    )


async def fetch_zzz_draw_data(
    agents: Sequence[ZZZFullAgent], *, template: Literal[1, 2, 3, 4]
) -> ZZZDrawData:
    agent_full_names: dict[int, AgentNameData] = {}

    async with hakushin.HakushinAPI(hakushin.Game.ZZZ) as api:
        characters = await api.fetch_characters()

        for agent in agents:
            chara_detail = await api.fetch_character_detail(agent.id)
            agent_full_names[agent.id] = AgentNameData(
                short_name=chara_detail.name,
                full_name=chara_detail.info.full_name
                if chara_detail.info is not None
                else chara_detail.name,
            )

        if template == 2:
            agent_images = {char.id: char.phase_3_cinema_art for char in characters}
        elif template == 1:
            agent_images = {char.id: char.image for char in characters}
        else:
            # 3, 4
            agent_images = {agent.id: agent.banner_icon for agent in agents}

        items = await api.fetch_items()
        disc_icons: dict[int, str] = {}
        for agent in agents:
            for disc in agent.discs:
                disc_item = next((item for item in items if item.id == disc.id), None)
                if disc_item is None:
                    continue
                disc_icons[disc.id] = disc_item.icon

    return ZZZDrawData(agent_full_names, agent_images, disc_icons)


async def draw_zzz_build_card(
    draw_input: DrawInput,
    agent: ZZZFullAgent,
    *,
    card_data: dict[str, Any],
    custom_color: str | None,
    custom_image: str | None,
    template: Literal[1, 2, 3, 4],
    show_substat_rolls: bool,
    agent_special_stat_map: dict[str, list[int]],
    hl_substats: list[int],
    hl_special_stats: bool,
) -> BytesIO:
    draw_data = await fetch_zzz_draw_data([agent], template=template)

    if template in {1, 2}:
        image = draw_data.agent_images[agent.id]
    else:  # 3, 4
        image = custom_image or draw_data.agent_images[agent.id]

    urls: list[str] = [image]
    urls.extend(draw_data.disc_icons.values())
    if agent.w_engine is not None:
        urls.append(agent.w_engine.icon)

    agent_special_stats = agent_special_stat_map.get(str(agent.id), [])

    if template == 3:
        folder = "zzz-team-card"
    elif template == 4:
        folder = "zzz-build-card4"
    else:  # 1, 2
        folder = "zzz-build-card"
    await download_images(urls, folder, draw_input.session)

    if template == 3:
        card = funcs.zzz.ZZZTeamCard(
            locale=draw_input.locale.value,
            agents=[agent],
            agent_colors={agent.id: custom_color or card_data["color"]},
            agent_images={agent.id: image},
            name_datas=draw_data.name_data,
            disc_icons=draw_data.disc_icons,
            show_substat_rolls={agent.id: show_substat_rolls},
            agent_special_stat_map=agent_special_stat_map,
            hl_special_stats={agent.id: hl_special_stats},
            agent_hl_substat_map={agent.id: hl_substats},
        )
    elif template == 4:
        card = funcs.zzz.ZZZAgentCard4(
            agent,
            locale=draw_input.locale.value,
            name_data=draw_data.name_data.get(agent.id),
            image_url=image,
            disc_icons=draw_data.disc_icons,
            color=custom_color or card_data["color"],
            show_substat_rolls=show_substat_rolls,
            agent_special_stats=agent_special_stats,
            hl_substats=hl_substats,
            hl_special_stats=hl_special_stats,
        )
    else:
        card = funcs.zzz.ZZZAgentCard(
            agent,
            locale=draw_input.locale.value,
            name_data=draw_data.name_data.get(agent.id),
            image_url=image,
            card_data=card_data,
            disc_icons=draw_data.disc_icons,
            color=custom_color,
            template=template,
            show_substat_rolls=show_substat_rolls,
            agent_special_stats=agent_special_stats,
            hl_special_stats=hl_special_stats,
            hl_substats=hl_substats,
        )
    return await draw_input.loop.run_in_executor(draw_input.executor, card.draw)


async def draw_zzz_characters_card(
    draw_input: DrawInput, agents: Sequence[ZZZFullAgent | UnownedZZZCharacter]
) -> File:
    urls: list[str] = []
    for agent in agents:
        urls.append(agent.banner_icon)
        if isinstance(agent, ZZZFullAgent) and agent.w_engine is not None:
            urls.append(agent.w_engine.icon)

    await download_images(urls, "zzz-characters", draw_input.session)
    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.zzz.draw_big_agent_card,
        agents,
        draw_input.dark_mode,
        draw_input.locale.value,
    )
    buffer.seek(0)

    return File(buffer, filename=draw_input.filename)


async def draw_honkai_suits_card(draw_input: DrawInput, suits: Sequence[FullBattlesuit]) -> File:
    urls: list[str] = []
    for suit in suits:
        urls.extend((suit.tall_icon.replace(" ", ""), suit.weapon.icon))
        urls.extend(stig.icon for stig in suit.stigmata)

    await download_images(urls, "honkai-characters", draw_input.session, ignore_error=True)

    buffer = await draw_input.loop.run_in_executor(
        draw_input.executor,
        funcs.hoyo.honkai.draw_big_suit_card,
        suits,
        draw_input.locale.value,
        draw_input.dark_mode,
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_zzz_team_card(
    draw_input: DrawInput,
    agents: Sequence[ZZZFullAgent],
    agent_colors: dict[int, str],
    agent_custom_images: dict[int, str],
    show_substat_rolls: dict[int, bool],
    agent_special_stat_map: dict[str, list[int]],
    agent_hl_substat_map: dict[int, list[int]],
    hl_special_stats: dict[int, bool],
) -> BytesIO:
    draw_data = await fetch_zzz_draw_data(agents, template=3)

    urls = list(agent_custom_images.values())
    urls.extend(agent.w_engine.icon for agent in agents if agent.w_engine is not None)
    urls.extend(draw_data.disc_icons.values())
    await download_images(urls, "zzz-team-card", draw_input.session)

    card = funcs.zzz.ZZZTeamCard(
        locale=draw_input.locale.value,
        agents=agents,
        agent_colors=agent_colors,
        agent_images=agent_custom_images,
        name_datas=draw_data.name_data,
        disc_icons=draw_data.disc_icons,
        show_substat_rolls=show_substat_rolls,
        agent_special_stat_map=agent_special_stat_map,
        hl_special_stats=hl_special_stats,
        agent_hl_substat_map=agent_hl_substat_map,
    )
    return await draw_input.loop.run_in_executor(draw_input.executor, card.draw)


async def draw_hsr_team_card(
    draw_input: DrawInput,
    characters: Sequence[HoyolabHSRCharacter | enka.hsr.Character],
    character_images: dict[str, str],
    character_colors: dict[str, str],
) -> BytesIO:
    urls: list[str] = list(character_images.values())
    for character in characters:
        if character.light_cone is not None:
            urls.append(character.light_cone.icon.image)
            if isinstance(character, enka.hsr.Character):
                urls.extend(stat.icon for stat in character.light_cone.stats)

        urls.extend(trace.icon for trace in character.traces)
        urls.extend(relic.icon for relic in character.relics)

        if isinstance(character, enka.hsr.Character):
            urls.extend(stat.icon for stat in character.stats.values())
        else:
            urls.extend(stat.icon for stat in character.stats)

    await download_images(urls, "hsr-team-card", draw_input.session)

    card = funcs.hsr.HSRTeamCard(
        locale=draw_input.locale.value,
        characters=characters,
        character_images=character_images,
        character_colors=character_colors,
    )
    return await draw_input.loop.run_in_executor(draw_input.executor, card.draw)


async def draw_gi_team_card(
    draw_input: DrawInput,
    characters: Sequence[enka.gi.Character | HoyolabGICharacter],
    character_images: dict[str, str],
) -> BytesIO:
    urls: list[str] = list(character_images.values())
    for character in characters:
        urls.extend(talent.icon for talent in character.talents)
        urls.extend(const.icon for const in character.constellations)
        urls.extend(artifact.icon for artifact in character.artifacts)
        urls.append(character.weapon.icon)

    await download_images(urls, "gi-team-card", draw_input.session)

    card = funcs.genshin.GITeamCard(
        locale=draw_input.locale.value,
        dark_mode=draw_input.dark_mode,
        characters=characters,
        character_images=character_images,
    )
    return await draw_input.loop.run_in_executor(draw_input.executor, card.draw)


async def draw_shiyu_card(
    draw_input: DrawInput,
    shiyu: genshin.models.ShiyuDefense,
    agent_ranks: dict[int, int],
    uid: int | None,
) -> File:
    urls = [
        character.icon
        for floor in shiyu.floors
        for character in floor.node_1.characters + floor.node_2.characters
    ]
    urls.extend(
        bangboo.icon
        for floor in shiyu.floors
        for bangboo in (floor.node_1.bangboo, floor.node_2.bangboo)
        if bangboo is not None
    )
    await download_images(urls, "shiyu", draw_input.session)

    card = funcs.zzz.ShiyuDefenseCard(shiyu, agent_ranks, uid, locale=draw_input.locale.value)
    buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)

    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_block_list_card(
    draw_input: DrawInput, block_lists: Sequence[Sequence[SingleBlock | DoubleBlock]]
) -> File:
    urls: list[str] = []
    for block_list in block_lists:
        for block in block_list:
            if isinstance(block, SingleBlock):
                urls.append(block.icon)
            else:
                urls.extend((block.icon1, block.icon2))

    await download_images(urls, "block-list", draw_input.session)

    card = funcs.block_list.BlockListCard(block_lists, dark_mode=draw_input.dark_mode)
    buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)
