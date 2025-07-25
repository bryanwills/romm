import asyncio
from enum import Enum
from typing import Any

import emoji
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler
from handler.filesystem import fs_asset_handler, fs_firmware_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import (
    meta_hasheous_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.metadata.hasheous_handler import HasheousRom
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.launchbox_handler import LaunchboxRom
from handler.metadata.moby_handler import MobyGamesRom
from handler.metadata.playmatch_handler import PlaymatchRomMatch
from handler.metadata.ra_handler import RAGameRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.metadata.ss_handler import SSRom
from logger.formatter import BLUE, LIGHTYELLOW
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom
from models.user import User

LOGGER_MODULE_NAME = {"module_name": "scan"}


class ScanType(Enum):
    NEW_PLATFORMS = "new_platforms"
    QUICK = "quick"
    UNIDENTIFIED = "unidentified"
    PARTIAL = "partial"
    COMPLETE = "complete"
    HASHES = "hashes"


class MetadataSource:
    IGDB = "igdb"  # IGDB
    MOBY = "moby"  # MobyGames
    SS = "ss"  # Screenscraper
    RA = "ra"  # RetroAchivements
    LB = "lb"  # Launchbox
    HASHEOUS = "hasheous"  # Hasheous
    TGDB = "tgdb"  # TheGamesDB
    SGDB = "sgdb"  # SteamGridDB


async def _get_main_platform_igdb_id(platform: Platform):
    cnfg = cm.get_config()

    if platform.fs_slug in cnfg.PLATFORMS_VERSIONS.keys():
        main_platform_slug = cnfg.PLATFORMS_VERSIONS[platform.fs_slug]
        main_platform = db_platform_handler.get_platform_by_fs_slug(main_platform_slug)
        if main_platform:
            main_platform_igdb_id = main_platform.igdb_id
        else:
            main_platform = await meta_igdb_handler.get_platform(main_platform_slug)
            main_platform_igdb_id = main_platform["igdb_id"]
            if not main_platform_igdb_id:
                main_platform_igdb_id = platform.igdb_id
    else:
        main_platform_igdb_id = platform.igdb_id
    return main_platform_igdb_id


async def scan_platform(
    fs_slug: str,
    fs_platforms: list[str],
) -> Platform:
    """Get platform details

    Args:
        fs_slug: short name of the platform
    Returns
        Platform object
    """
    platform_attrs: dict[str, Any] = {}
    platform_attrs["fs_slug"] = fs_slug

    cnfg = cm.get_config()
    swapped_platform_bindings = {v: k for k, v in cnfg.PLATFORMS_BINDING.items()}
    swapped_platform_versions = {v: k for k, v in cnfg.PLATFORMS_VERSIONS.items()}

    # Sometimes users change the name of the folder, so we try to match it with the config
    if fs_slug not in fs_platforms:
        log.warning(
            f"{hl(fs_slug)} not found in file system, trying to match via config",
            extra=LOGGER_MODULE_NAME,
        )
        if fs_slug in swapped_platform_bindings.keys():
            platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = swapped_platform_bindings[platform.slug]
        elif fs_slug in swapped_platform_versions.keys():
            platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = swapped_platform_versions[platform.slug]

    try:
        if fs_slug in cnfg.PLATFORMS_BINDING.keys():
            platform_attrs["slug"] = cnfg.PLATFORMS_BINDING[fs_slug]
        elif fs_slug in cnfg.PLATFORMS_VERSIONS.keys():
            platform_attrs["slug"] = cnfg.PLATFORMS_VERSIONS[fs_slug]
        else:
            platform_attrs["slug"] = fs_slug
    except (KeyError, TypeError, AttributeError):
        platform_attrs["slug"] = fs_slug

    igdb_platform = await meta_igdb_handler.get_platform(platform_attrs["slug"])
    moby_platform = meta_moby_handler.get_platform(platform_attrs["slug"])
    ss_platform = meta_ss_handler.get_platform(platform_attrs["slug"])
    ra_platform = meta_ra_handler.get_platform(platform_attrs["slug"])
    launchbox_platform = meta_launchbox_handler.get_platform(platform_attrs["slug"])
    hasheous_platform = meta_hasheous_handler.get_platform(platform_attrs["slug"])
    tgdb_platform = meta_tgdb_handler.get_platform(platform_attrs["slug"])

    platform_attrs["name"] = platform_attrs["slug"].replace("-", " ").title()
    platform_attrs.update(
        {
            **hasheous_platform,
            **tgdb_platform,
            **launchbox_platform,
            **ra_platform,
            **moby_platform,
            **ss_platform,
            **igdb_platform,
            "igdb_id": igdb_platform.get("igdb_id")
            or hasheous_platform.get("igdb_id")
            or None,
            "ra_id": ra_platform.get("ra_id") or hasheous_platform.get("ra_id") or None,
            "tgdb_id": moby_platform.get("tgdb_id")
            or hasheous_platform.get("tgdb_id")
            or None,
            "name": igdb_platform.get("name")
            or ss_platform.get("name")
            or moby_platform.get("name")
            or ra_platform.get("name")
            or launchbox_platform.get("name")
            or hasheous_platform.get("name")
            or tgdb_platform.get("name")
            or platform_attrs["slug"].replace("-", " ").title(),
            "url_logo": igdb_platform.get("url_logo")
            or tgdb_platform.get("url_logo")
            or "",
        }
    )

    if (
        platform_attrs["igdb_id"]
        or platform_attrs["moby_id"]
        or platform_attrs["ss_id"]
        or platform_attrs["ra_id"]
        or platform_attrs["launchbox_id"]
        or hasheous_platform["hasheous_id"]
        or tgdb_platform["tgdb_id"]
    ):
        log.info(
            emoji.emojize(
                f"Folder {hl(platform_attrs['slug'])}[{hl(fs_slug, color=LIGHTYELLOW)}] identified as {hl(platform_attrs['name'], color=BLUE)} :video_game:"
            ),
            extra={"module_name": "scan"},
        )
    else:
        log.warning(
            emoji.emojize(
                f"Platform {hl(platform_attrs['slug'])} not identified :cross_mark:"
            ),
            extra=LOGGER_MODULE_NAME,
        )

    platform_attrs["missing_from_fs"] = False
    return Platform(**platform_attrs)


async def scan_firmware(
    platform: Platform,
    file_name: str,
    firmware: Firmware | None = None,
) -> Firmware:
    firmware_path = fs_firmware_handler.get_firmware_fs_structure(platform.fs_slug)

    # Set default properties
    firmware_attrs = {
        "id": firmware.id if firmware else None,
        "platform_id": platform.id,
    }

    file_path = f"{firmware_path}/{file_name}"
    file_size = await fs_firmware_handler.get_file_size(file_path)

    firmware_attrs.update(
        {
            "file_path": firmware_path,
            "file_name": file_name,
            "file_name_no_tags": fs_firmware_handler.get_file_name_with_no_tags(
                file_name
            ),
            "file_name_no_ext": fs_firmware_handler.get_file_name_with_no_extension(
                file_name
            ),
            "file_extension": fs_firmware_handler.parse_file_extension(file_name),
            "file_size_bytes": file_size,
        }
    )

    file_hashes = await fs_firmware_handler.calculate_file_hashes(
        firmware_path=firmware_path,
        file_name=file_name,
    )

    firmware_attrs.update(**file_hashes)

    return Firmware(**firmware_attrs)


async def scan_rom(
    scan_type: ScanType,
    platform: Platform,
    rom: Rom,
    fs_rom: FSRom,
    metadata_sources: list[str],
    newly_added: bool,
) -> Rom:
    if not metadata_sources:
        log.error("No metadata sources provided")
        raise ValueError("No metadata sources provided")

    filesize = sum([file.file_size_bytes for file in fs_rom["files"]])
    rom_attrs = {
        "platform_id": platform.id,
        "name": fs_rom["fs_name"],
        "fs_name": fs_rom["fs_name"],
        "multi": fs_rom["multi"],
        "crc_hash": fs_rom["crc_hash"],
        "md5_hash": fs_rom["md5_hash"],
        "sha1_hash": fs_rom["sha1_hash"],
        "ra_hash": fs_rom["ra_hash"],
        "fs_size_bytes": filesize,
        "url_cover": "",
        "url_manual": "",
        "url_screenshots": [],
    }

    if rom:
        rom_attrs.update(
            {
                "id": rom.id,
                "fs_path": rom.fs_path,
                "fs_name_no_tags": rom.fs_name_no_tags,
                "fs_name_no_ext": rom.fs_name_no_ext,
                "fs_extension": rom.fs_extension,
                "regions": rom.regions,
                "revision": rom.revision,
                "languages": rom.languages,
                "tags": rom.tags,
            }
        )

    # Update properties from existing rom if not a complete rescan
    if not newly_added and scan_type != ScanType.COMPLETE:
        rom_attrs.update(
            {
                "igdb_id": rom.igdb_id,
                "moby_id": rom.moby_id,
                "ss_id": rom.ss_id,
                "sgdb_id": rom.sgdb_id,
                "ra_id": rom.ra_id,
                "launchbox_id": rom.launchbox_id,
                "hasheous_id": rom.hasheous_id,
                "tgdb_id": rom.tgdb_id,
                "name": rom.name,
                "slug": rom.slug,
                "summary": rom.summary,
                "igdb_metadata": rom.igdb_metadata,
                "moby_metadata": rom.moby_metadata,
                "ss_metadata": rom.ss_metadata,
                "ra_metadata": rom.ra_metadata,
                "launchbox_metadata": rom.launchbox_metadata,
                "hasheous_metadata": rom.hasheous_metadata,
                "path_cover_s": rom.path_cover_s,
                "path_cover_l": rom.path_cover_l,
                "path_screenshots": rom.path_screenshots,
                "path_manual": rom.path_manual,
                "url_cover": rom.url_cover,
                "url_screenshots": rom.url_screenshots,
                "url_manual": rom.url_manual,
            }
        )

    async def fetch_playmatch_hash_match() -> PlaymatchRomMatch:
        if (
            MetadataSource.IGDB in metadata_sources
            and platform.igdb_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.igdb_id)
                or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
            )
        ):
            return await meta_playmatch_handler.lookup_rom(fs_rom["files"])

        return PlaymatchRomMatch(igdb_id=None)

    async def fetch_hasheous_hash_match() -> HasheousRom:
        if (
            MetadataSource.HASHEOUS in metadata_sources
            and platform.hasheous_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.hasheous_id)
                or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
            )
        ):
            return await meta_hasheous_handler.lookup_rom(
                platform.slug, fs_rom["files"]
            )

        return HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)

    # Run hash fetches concurrently
    (
        playmatch_hash_match,
        hasheous_hash_match,
    ) = await asyncio.gather(
        fetch_playmatch_hash_match(),
        fetch_hasheous_hash_match(),
    )

    async def fetch_igdb_rom(
        playmatch_rom: PlaymatchRomMatch, hasheous_rom: HasheousRom
    ) -> IGDBRom:
        if (
            MetadataSource.IGDB in metadata_sources
            and platform.igdb_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.igdb_id)
                or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
            )
        ):
            # Use Hasheous match to get the IGDB ID
            h_igdb_id = hasheous_rom.get("igdb_id")
            if h_igdb_id:
                log.debug(
                    emoji.emojize(
                        f"{hl(rom_attrs['fs_name'])} identified by Hasheous as "
                        f"{hl(str(h_igdb_id), color=BLUE)} :alien_monster:"
                    ),
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_igdb_handler.get_rom_by_id(h_igdb_id)

            # Use Playmatch matches to get the IGDB ID
            if playmatch_rom["igdb_id"] is not None:
                log.debug(
                    emoji.emojize(
                        f"{hl(rom_attrs['fs_name'])} identified by Playmatch as "
                        f"{hl(str(playmatch_rom["igdb_id"]), color=BLUE)} :alien_monster:"
                    ),
                    extra=LOGGER_MODULE_NAME,
                )

                return await meta_igdb_handler.get_rom_by_id(playmatch_rom["igdb_id"])

            # If no matches found, use the file name to get the IGDB ID
            main_platform_igdb_id = await _get_main_platform_igdb_id(platform)
            return await meta_igdb_handler.get_rom(
                rom_attrs["fs_name"], main_platform_igdb_id or platform.igdb_id
            )

        return IGDBRom(igdb_id=None)

    async def fetch_moby_rom() -> MobyGamesRom:
        if (
            MetadataSource.MOBY in metadata_sources
            and platform.moby_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.moby_id)
                or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
            )
        ):
            return await meta_moby_handler.get_rom(
                rom_attrs["fs_name"], platform_moby_id=platform.moby_id
            )

        return MobyGamesRom(moby_id=None)

    async def fetch_ss_rom() -> SSRom:
        if (
            MetadataSource.SS in metadata_sources
            and platform.ss_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.ss_id)
                or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
            )
        ):
            return await meta_ss_handler.get_rom(
                rom_attrs["fs_name"], platform_ss_id=platform.ss_id
            )

        return SSRom(ss_id=None)

    async def fetch_launchbox_rom(platform_slug: str) -> LaunchboxRom:
        if MetadataSource.LB in metadata_sources and (
            newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.PARTIAL and not rom.launchbox_id)
            or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
        ):
            return await meta_launchbox_handler.get_rom(
                rom_attrs["fs_name"], platform_slug
            )

        return LaunchboxRom(launchbox_id=None)

    async def fetch_ra_rom(hasheous_rom: HasheousRom) -> RAGameRom:
        if (
            MetadataSource.RA in metadata_sources
            and platform.ra_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or scan_type == ScanType.HASHES
                or (scan_type == ScanType.PARTIAL and not rom.ra_id)
                or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
            )
        ):
            # Use Hasheous match to get the IGDB ID
            h_ra_id = hasheous_rom.get("ra_id")
            if h_ra_id:
                log.debug(
                    emoji.emojize(
                        f"{hl(rom_attrs['fs_name'])} identified by Hasheous as "
                        f"{hl(str(h_ra_id), color=BLUE)} :alien_monster:"
                    ),
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_ra_handler.get_rom_by_id(rom=rom, ra_id=h_ra_id)

            return await meta_ra_handler.get_rom(rom=rom, ra_hash=rom_attrs["ra_hash"])

        return RAGameRom(ra_id=None)

    async def fetch_hasheous_rom(hasheous_rom: HasheousRom) -> HasheousRom:
        if (
            MetadataSource.HASHEOUS in metadata_sources
            and platform.hasheous_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.hasheous_id)
                or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
            )
        ):
            (
                igdb_game,
                ra_game,
            ) = await asyncio.gather(
                meta_hasheous_handler.get_igdb_game(hasheous_rom),
                meta_hasheous_handler.get_ra_game(hasheous_rom),
            )

            return HasheousRom(
                {
                    **hasheous_rom,
                    **ra_game,
                    **igdb_game,
                }
            )

        return HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)

    # Run metadata fetches concurrently
    (
        igdb_handler_rom,
        moby_handler_rom,
        ss_handler_rom,
        ra_handler_rom,
        launchbox_handler_rom,
        hasheous_handler_rom,
    ) = await asyncio.gather(
        fetch_igdb_rom(playmatch_hash_match, hasheous_hash_match),
        fetch_moby_rom(),
        fetch_ss_rom(),
        fetch_ra_rom(hasheous_hash_match),
        fetch_launchbox_rom(platform.slug),
        fetch_hasheous_rom(hasheous_hash_match),
    )

    # Only update fields if match is found
    if launchbox_handler_rom.get("launchbox_id"):
        rom_attrs.update({**launchbox_handler_rom})
    if hasheous_handler_rom.get("hasheous_id"):
        rom_attrs.update({**hasheous_handler_rom})
    if ra_handler_rom.get("ra_id"):
        rom_attrs.update({**ra_handler_rom})
    if moby_handler_rom.get("moby_id"):
        rom_attrs.update({**moby_handler_rom})
    if ss_handler_rom.get("ss_id"):
        rom_attrs.update({**ss_handler_rom})
    if igdb_handler_rom.get("igdb_id"):
        rom_attrs.update({**igdb_handler_rom})

    # Stop IDs from getting overridden by empty values
    rom_attrs.update(
        {
            "igdb_id": igdb_handler_rom.get("igdb_id")
            or hasheous_handler_rom.get("igdb_id")
            or rom_attrs.get("igdb_id")
            or None,
            "ss_id": ss_handler_rom.get("ss_id") or rom_attrs.get("ss_id") or None,
            "moby_id": moby_handler_rom.get("moby_id")
            or rom_attrs.get("moby_id")
            or None,
            "ra_id": ra_handler_rom.get("ra_id")
            or hasheous_handler_rom.get("ra_id")
            or rom_attrs.get("ra_id")
            or None,
            "launchbox_id": launchbox_handler_rom.get("launchbox_id")
            or rom_attrs.get("launchbox_id")
            or None,
            "hasheous_id": hasheous_handler_rom.get("hasheous_id")
            or rom_attrs.get("hasheous_id")
            or None,
            "tgdb_id": hasheous_handler_rom.get("tgdb_id")
            or rom_attrs.get("tgdb_id")
            or None,
        }
    )

    # Don't overwrite existing fields on partial scans
    if not newly_added and scan_type == ScanType.PARTIAL:
        rom_attrs.update(
            {
                "name": rom.name or rom_attrs.get("name") or None,
                "summary": rom.summary or rom_attrs.get("summary") or None,
                "url_cover": rom.url_cover or rom_attrs.get("url_cover") or None,
                "url_manual": rom.url_manual or rom_attrs.get("url_manual") or None,
                "url_screenshots": rom.url_screenshots
                or rom_attrs.get("url_screenshots")
                or [],
            }
        )

    # If not found in any metadata source, we return the rom with the default values
    if (
        not igdb_handler_rom.get("igdb_id")
        and not moby_handler_rom.get("moby_id")
        and not ss_handler_rom.get("ss_id")
        and not ra_handler_rom.get("ra_id")
        and not launchbox_handler_rom.get("launchbox_id")
        and not hasheous_handler_rom.get("hasheous_id")
    ):
        log.warning(
            emoji.emojize(f"{hl(rom_attrs['fs_name'])} not identified :cross_mark:"),
            extra=LOGGER_MODULE_NAME,
        )
        return Rom(**rom_attrs)

    async def fetch_sgdb_details() -> SGDBRom:
        """Fetch SteamGridDB details for the ROM."""
        if (
            MetadataSource.SGDB in metadata_sources
            and newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.PARTIAL and not rom.sgdb_id)
            or (scan_type == ScanType.UNIDENTIFIED and rom.is_unidentified)
        ):
            game_names = [
                igdb_handler_rom.get("name", None),
                hasheous_handler_rom.get("name", None),
                ss_handler_rom.get("name", None),
                moby_handler_rom.get("name", None),
                launchbox_handler_rom.get("name", None),
                rom_attrs["fs_name_no_tags"],
            ]
            game_names = [name for name in game_names if name]
            return await meta_sgdb_handler.get_details_by_names(game_names)

        return SGDBRom(sgdb_id=None)

    sgdb_hander_rom = await fetch_sgdb_details()
    if sgdb_hander_rom.get("sgdb_id"):
        rom_attrs.update({**sgdb_hander_rom})

    log.info(
        emoji.emojize(
            f"{hl(rom_attrs['fs_name'])} identified as {hl(rom_attrs['name'], color=BLUE)} :alien_monster:"
        ),
        extra=LOGGER_MODULE_NAME,
    )
    if rom.multi:
        for file in fs_rom["files"]:
            log.info(
                f"\t · {hl(file.file_name, color=LIGHTYELLOW)}",
                extra=LOGGER_MODULE_NAME,
            )

    rom_attrs["missing_from_fs"] = False
    return Rom(**rom_attrs)


async def _scan_asset(file_name: str, asset_path: str):
    file_path = f"{asset_path}/{file_name}"
    file_size = await fs_asset_handler.get_file_size(file_path)

    return {
        "file_path": asset_path,
        "file_name": file_name,
        "file_name_no_tags": fs_asset_handler.get_file_name_with_no_tags(file_name),
        "file_name_no_ext": fs_asset_handler.get_file_name_with_no_extension(file_name),
        "file_extension": fs_asset_handler.parse_file_extension(file_name),
        "file_size_bytes": file_size,
    }


async def scan_save(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> Save:
    saves_path = fs_asset_handler.build_saves_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    scanned_asset = await _scan_asset(file_name, saves_path)
    return Save(**scanned_asset)


async def scan_state(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> State:
    states_path = fs_asset_handler.build_states_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    scanned_asset = await _scan_asset(file_name, states_path)
    return State(**scanned_asset)


async def scan_screenshot(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
) -> Screenshot:
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
    )
    scanned_asset = await _scan_asset(file_name, screenshots_path)
    return Screenshot(**scanned_asset)
