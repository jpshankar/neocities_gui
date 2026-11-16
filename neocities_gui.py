import configparser, flet, os

from neocities_api import list_files as neocities_api_list, info as neocities_api_info, download_file as neocities_download_file, ROOT_DIR as NEOCITIES_LIST_ROOT, NeocitiesDirectory, NeocitiesDirectoryEntry, NeocitiesDirectoryContent

from functools import partial
from itertools import batched

from dataclasses import dataclass

GUI_WIDTH = 600
GUI_HEIGHT = 400

GUI_TITLE = "Neocities GUI"

SETTINGS_ICON = flet.Icons.SETTINGS

BACK_ARROW_ICON = flet.Icons.ARROW_BACK
FORWARD_ARROW_ICON = flet.Icons.ARROW_FORWARD

DIRECTORY_ICON_DOWNLOAD = flet.Icons.FOLDER
DIRECTORY_ICON_NO_DOWNLOAD = flet.Icons.FOLDER_OUTLINED

FILE_ICON_DOWNLOAD = flet.Icons.INSERT_DRIVE_FILE
FILE_ICON_NO_DOWNLOAD = flet.Icons.INSERT_DRIVE_FILE_OUTLINED

SETTINGS_FILE = "settings.ini"

SETTINGS_FILE_DEFAULT = "DEFAULT"

SETTINGS_FILE_API_KEY = "API_KEY"
SETTINGS_FILE_DOWNLOAD_DIRECTORY = "DOWNLOAD_DIRECTORY"

FILE_LIST_PAGE_NUM_ITEMS = 5

DOWNLOAD_BUTTONS_SELECT_ALL_VISIBLE_OFFSET = flet.Offset(x = 0.36, y = 0)
DOWNLOAD_BUTTONS_DESELECT_ALL_VISIBLE_OFFSET = flet.Offset(x = 0.30, y = 0)

DOWNLOAD_BUTTONS_NO_TEXT_VISIBLE_OFFSET = flet.Offset(x = 0.78, y = 0)

DOWNLOAD_BUTTONS_INVISIBLE_OFFSET = flet.Offset(x = 0.96, y = 0)

SELECT_ALL_BUTTON_TEXT = "Select All"
DESELECT_ALL_BUTTON_TEXT = "Deselect All"

DISPLAY_COLUMN_HEIGHT = 250

COLLECTING_FILES = "Collecting file information for download.."

@dataclass(frozen=True)
class DirectorySoFar:
    directory: NeocitiesDirectory
    path_so_far: str

@dataclass(frozen=True)
class FileToDownload:
    path_to_file: str
    file_name: str

    file_size: int

async def main(page: flet.Page):
    download_tab = flet.Tab(label = "Download")
    tab_bar = flet.TabBar(tabs = [download_tab])

    tabs = flet.Tabs(
        content = flet.Row(controls = [tab_bar]),
        length = 2
    )

    display_column = flet.Column(width = GUI_WIDTH, height = DISPLAY_COLUMN_HEIGHT)
    
    storage_paths = flet.StoragePaths()

    settings_file_directory = await storage_paths.get_application_support_directory()
    settings_file_path = f"{settings_file_directory}\\{SETTINGS_FILE}"

    settings_file_config = configparser.ConfigParser()

    directory_pages = {}
    directory_names = {}

    directory_download_files = {}

    directory_entry_icons = {}

    download_display_text = flet.Text()
    download_display_progress_bar = flet.ProgressBar(width = GUI_WIDTH)

    download_display_progress_text = flet.Text(value = COLLECTING_FILES)

    download_button = flet.TextButton(visible = False)

    next_page_button = flet.IconButton(icon = FORWARD_ARROW_ICON, visible = False)
    previous_page_button = flet.IconButton(icon = BACK_ARROW_ICON, visible = False)

    settings_button = flet.IconButton(icon = SETTINGS_ICON)

    settings_download_directory_button = flet.IconButton(icon = DIRECTORY_ICON_DOWNLOAD, align = flet.Alignment.CENTER)
    
    settings_download_directory_picker = flet.FilePicker()

    async def settings_button_clicked(current_directory: NeocitiesDirectory):
        if settings_button.icon == SETTINGS_ICON:
            display_column.controls = [settings_api_key, settings_download_directory_row]

            if settings_api_key_input:
                settings_api_key.value = settings_api_key_input
            elif os.path.exists(settings_file_path):
                settings_file_config.read(settings_file_path)
                default_settings = settings_file_config[SETTINGS_FILE_DEFAULT]

                if SETTINGS_FILE_API_KEY in default_settings:
                    settings_api_key.value = default_settings[SETTINGS_FILE_API_KEY]

                if SETTINGS_FILE_DOWNLOAD_DIRECTORY in default_settings:
                    settings_download_directory.value = default_settings[SETTINGS_FILE_DOWNLOAD_DIRECTORY]

            buttons_row.offset = DOWNLOAD_BUTTONS_INVISIBLE_OFFSET

            settings_button.icon = BACK_ARROW_ICON
            go_from_download()
        elif settings_button.icon == BACK_ARROW_ICON:
            if settings_api_key.error:
                settings_api_key.error = None

            download_directory_set = SETTINGS_FILE_DOWNLOAD_DIRECTORY in settings_file_config[SETTINGS_FILE_DEFAULT]

            if current_directory in directory_names and current_directory in directory_pages:
                display_column.controls = [directory_names[current_directory], directory_pages[current_directory]]

                if download_directory_set:
                    buttons_row.offset = DOWNLOAD_BUTTONS_SELECT_ALL_VISIBLE_OFFSET if toggle_all_none_button.content == SELECT_ALL_BUTTON_TEXT else DOWNLOAD_BUTTONS_DESELECT_ALL_VISIBLE_OFFSET
                else:
                    buttons_row.offset = DOWNLOAD_BUTTONS_NO_TEXT_VISIBLE_OFFSET
            else: 
                display_column.controls = []
            
            settings_button.icon = SETTINGS_ICON

            go_to_download(download_directory_set = download_directory_set)
        
    async def handle_picking_download_directory(current_directory: NeocitiesDirectory | None):
        download_directory = await settings_download_directory_picker.get_directory_path()
        if download_directory:
            settings_download_directory.value = download_directory

            default_config = settings_file_config[SETTINGS_FILE_DEFAULT]

            download_directory_already_set = SETTINGS_FILE_DOWNLOAD_DIRECTORY in default_config

            if not download_directory_already_set:
                for subdirectory_pages in directory_pages.values():
                    for subdirectory_page in subdirectory_pages.controls:
                        for subdirectory_page_row in subdirectory_page.controls:
                            subdirectory_page_row.controls[0].disabled = False

            settings_file_config[SETTINGS_FILE_DEFAULT][SETTINGS_FILE_DOWNLOAD_DIRECTORY] = download_directory

            with open(settings_file_path, "w") as settings_file:
                settings_file_config.write(settings_file)

            if download_button.disabled:
                download_button.disabled = False

            if toggle_all_none_button.disabled:
                toggle_all_none_button.disabled = False

            if current_directory and not settings_button.on_click:
                settings_button.on_click = partial(settings_button_clicked, current_directory)
                
    toggle_all_none_button = flet.TextButton(visible = False)

    buttons_row = flet.Row(controls = [toggle_all_none_button, download_button, previous_page_button, next_page_button, settings_button], width = GUI_WIDTH, height = 25, offset = DOWNLOAD_BUTTONS_INVISIBLE_OFFSET)

    def _calculate_num_files():
        num_files_to_download = 0
        for subdirectory_pages in directory_pages.values():
            for subdirectory_page in subdirectory_pages.controls:
                num_files = len([subdirectory_page_row for subdirectory_page_row in subdirectory_page.controls if subdirectory_page_row.controls[0].icon == FILE_ICON_DOWNLOAD])
                num_files_to_download+=num_files

        return num_files_to_download

    def set_download_button():
        num_files = _calculate_num_files()

        if num_files > 0 and download_button.disabled:
            download_button.disabled = False
        elif num_files == 0 and not download_button.disabled:
            download_button.disabled = True

        download_button.content = f"Download {num_files} files"

    def set_download_text(download_location: str):
        download_display_text.value = f"Downloading {_calculate_num_files()} files to {download_location}"

    async def go_to_next_page(page_view: flet.PageView):
        next_page_ind = page_view.selected_index + 1

        if next_page_ind == len(page_view.controls) - 1:
            next_page_button.disabled = True

        if previous_page_button.disabled:
            previous_page_button.disabled = False
            
        await page_view.jump_to_page(next_page_ind)

    async def go_to_previous_page(page_view: flet.PageView):
        previous_page_ind = page_view.selected_index - 1

        if previous_page_ind == 0:
            previous_page_button.disabled = True

        if next_page_button.disabled:
            next_page_button.disabled = False
            
        await page_view.jump_to_page(previous_page_ind)

    def go_from_download():
        if next_page_button.visible:
            next_page_button.visible = False

        if previous_page_button.visible:
            previous_page_button.visible = False

        if download_button.visible:
            download_button.visible = False

        if toggle_all_none_button.visible:
            toggle_all_none_button.visible = False

    def go_to_download(download_directory_set: bool):
        if directory_pages and directory_names:
            next_page_button.visible = True
            previous_page_button.visible = True

            if download_directory_set:
                download_button.visible = True

                toggle_all_none_button.visible = True

    def make_download_files_on_click(current_directory: NeocitiesDirectory):
        default_config = settings_file_config[SETTINGS_FILE_DEFAULT]
        download_directory = default_config[SETTINGS_FILE_DOWNLOAD_DIRECTORY]

        def hide_buttons_row():
            buttons_row.visible = False
            buttons_row.update()


        # Logic here run via generator: https://flet.dev/docs/cookbook/auto-update/#updating-part-way-through-a-handler
        def set_up_files_download_ui():
            go_from_download()

            set_download_text(download_location = download_directory)
            download_display_text.visible = True

            display_column.controls = [download_display_text, download_display_progress_bar, download_display_progress_text]
            display_column.update()

        directories_to_process = [DirectorySoFar(directory = NEOCITIES_LIST_ROOT, path_so_far = "")]
        directory_files_to_process = []

        download_files_to_icons = {}

        while directories_to_process:
            directory_to_process = directories_to_process.pop()
            relevant_directory = directory_to_process.directory

            directory_files = directory_download_files[relevant_directory]
            directory_path_so_far = directory_to_process.path_so_far

            for directory_file in directory_files:
                relevant_path_so_far = f"{directory_path_so_far}\\" if directory_path_so_far else ""
                relevant_directory_filename = relevant_directory.filename if relevant_directory != NEOCITIES_LIST_ROOT else ""

                path_to_directory_file = f"{relevant_path_so_far}{relevant_directory_filename}"

                if isinstance(directory_file, NeocitiesDirectoryEntry):
                    directory_file_to_download = FileToDownload(path_to_file = path_to_directory_file, file_name = directory_file.filename, file_size = directory_file.size_in_bytes)
                    directory_files_to_process.append(directory_file_to_download)
                
                    download_files_to_icons[directory_file_to_download] = directory_entry_icons[directory_file]
                elif isinstance(directory_file, NeocitiesDirectory):
                    directories_to_process.append(DirectorySoFar(directory = directory_file, path_so_far = path_to_directory_file))

        files_largest_to_smallest = sorted(directory_files_to_process, key = lambda d: d.file_size, reverse = True)
        api_key = default_config[SETTINGS_FILE_API_KEY]

        download_files_ui_updates = [hide_buttons_row, set_up_files_download_ui]

        def handle_file(file_to_download: FileToDownload):
            file_icon = download_files_to_icons[file_to_download]

            if file_icon.icon == FILE_ICON_DOWNLOAD:
                path_to_directory_file = file_to_download.path_to_file
                file_name = file_to_download.file_name

                file_directory_path = f"{download_directory}\\{path_to_directory_file}"
                file_full_path = f"{file_directory_path}\\{file_name}"

                download_display_progress_text.value = f"Downloading file: {file_full_path}"
                download_display_progress_text.update()

                neocities_file_path = f"{path_to_directory_file}/{file_name}".replace("\\", "/")
                downloaded_file = neocities_download_file(api_key = api_key, path_to_file = neocities_file_path)

                if not os.path.exists(file_directory_path):
                    os.makedirs(file_directory_path)

                with open(file_full_path, "wb") as downloaded_fp:
                    downloaded_fp.write(downloaded_file)

        for file_to_download in files_largest_to_smallest:
            download_file_update = partial(handle_file, file_to_download = file_to_download)
            download_files_ui_updates.append(download_file_update)

        def tear_down_file_download_ui():
            display_column.controls = [directory_names[current_directory], directory_pages[current_directory]]

            go_to_download(download_directory_set = True)
            
            buttons_row.visible = True
            buttons_row.update()

        download_files_ui_updates.append(tear_down_file_download_ui)

        def download_files():
            for download_files_ui_update in download_files_ui_updates:
                download_files_ui_update()
                yield

        return download_files

    def set_up_navigation_buttons(page_view: flet.PageView):
        more_than_one_page = len(page_view.controls) > 1
        if len(page_view.controls) > 1:
            async def entry_next_page():
                await go_to_next_page(page_view = page_view)

            async def entry_previous_page():
                await go_to_previous_page(page_view = page_view)

            next_page_button.on_click = entry_next_page
            previous_page_button.on_click = entry_previous_page
            
        next_page_button.disabled = not more_than_one_page
        previous_page_button.disabled = True

    def set_up_download_button(page_directory: NeocitiesDirectory):
        on_click_download_files = make_download_files_on_click(current_directory = page_directory)
        download_button.on_click = on_click_download_files
            
    def go_to_page_entry_directory(page_entry_directory: NeocitiesDirectory, download_directory_set: bool):
        entry_pages = directory_pages[page_entry_directory]
        display_column.controls = [directory_names[page_entry_directory], entry_pages]

        set_up_navigation_buttons(page_view = entry_pages)
        if download_directory_set:
            set_up_download_button(page_directory = page_entry_directory)

        settings_button.on_click = partial(settings_button_clicked, page_entry_directory)
        settings_download_directory_button.on_click = partial(handle_picking_download_directory, page_entry_directory)

    def toggle_downloading_directory_entry(directory_entry: NeocitiesDirectoryContent, parent_directory: NeocitiesDirectory | None = None):
        directory_entry_icon_button = directory_entry_icons[directory_entry]
        parent_directory_icon_button = directory_entry_icons[parent_directory] if parent_directory else None

        if parent_directory_icon_button:
            if parent_directory_icon_button.icon == DIRECTORY_ICON_DOWNLOAD:
                if isinstance(directory_entry, NeocitiesDirectoryEntry) and directory_entry_icon_button.icon == FILE_ICON_NO_DOWNLOAD: 
                    directory_entry_icon_button.icon = FILE_ICON_DOWNLOAD
                elif isinstance(directory_entry, NeocitiesDirectory) and directory_entry_icon_button.icon == DIRECTORY_ICON_NO_DOWNLOAD:
                    directory_entry_icon_button.icon = DIRECTORY_ICON_DOWNLOAD
            elif parent_directory_icon_button.icon == DIRECTORY_ICON_NO_DOWNLOAD:
                if isinstance(directory_entry, NeocitiesDirectoryEntry) and directory_entry_icon_button.icon == FILE_ICON_DOWNLOAD: 
                    directory_entry_icon_button.icon = FILE_ICON_NO_DOWNLOAD
                elif isinstance(directory_entry, NeocitiesDirectory) and directory_entry_icon_button.icon == DIRECTORY_ICON_DOWNLOAD:
                    directory_entry_icon_button.icon = DIRECTORY_ICON_NO_DOWNLOAD
        else:
            if directory_entry_icon_button.icon == DIRECTORY_ICON_DOWNLOAD:
                directory_entry_icon_button.icon = DIRECTORY_ICON_NO_DOWNLOAD
            elif directory_entry_icon_button.icon == DIRECTORY_ICON_NO_DOWNLOAD:
                directory_entry_icon_button.icon = DIRECTORY_ICON_DOWNLOAD
            elif directory_entry_icon_button.icon == FILE_ICON_DOWNLOAD:
                directory_entry_icon_button.icon = FILE_ICON_NO_DOWNLOAD
            elif directory_entry_icon_button.icon == FILE_ICON_NO_DOWNLOAD:
                directory_entry_icon_button.icon = FILE_ICON_DOWNLOAD

    def toggle_downloading_directory_entries(directory: NeocitiesDirectory):
        directory_entries = directory_download_files[directory]

        subdirectory_entries = []
        directory_sub_entries = []

        for directory_entry in directory_entries:
            if isinstance(directory_entry, NeocitiesDirectory):
                subdirectory_entries.append(directory_entry)

            directory_sub_entries.append(directory_entry)

        while subdirectory_entries:
            subdirectory_entry = subdirectory_entries.pop(0)
            subdirectory_files = directory_download_files[subdirectory_entry]

            for subdirectory_file in subdirectory_files:
                if isinstance(subdirectory_file, NeocitiesDirectory):
                    subdirectory_entries.append(subdirectory_file)
                    
                directory_sub_entries.append(subdirectory_file)

        toggle_downloading_directory_entry(directory_entry = directory)

        for directory_sub_entry in directory_sub_entries:
            toggle_downloading_directory_entry(directory_entry = directory_sub_entry, parent_directory = directory)

        set_download_button()

    def on_click_file_entry(file_entry: NeocitiesDirectoryEntry):
        toggle_downloading_directory_entry(directory_entry = file_entry)
        set_download_button()

    def make_directory_displays(directory: NeocitiesDirectory, parent_directory: NeocitiesDirectory | None, directory_entries: list[NeocitiesDirectoryContent], relevant_api_key: str, download_directory_set: bool):
        pages = []

        for page_entries in batched(directory_entries, FILE_LIST_PAGE_NUM_ITEMS):
            page_entry_rows = []

            for page_entry in page_entries:
                is_directory = isinstance(page_entry, NeocitiesDirectory)

                page_entry_icon = flet.IconButton(disabled = not download_directory_set)
                page_entry_text = flet.TextButton(content = page_entry.filename, disabled = not is_directory)

                if is_directory:
                    page_entry_icon.icon = DIRECTORY_ICON_DOWNLOAD

                    page_entry_text.on_click = partial(go_to_page_entry_directory, page_entry, download_directory_set)
                    page_entry_icon.on_click = partial(toggle_downloading_directory_entries, page_entry)
                elif isinstance(page_entry, NeocitiesDirectoryEntry):
                    page_entry_icon.icon = FILE_ICON_DOWNLOAD

                    page_entry_icon.on_click = partial(on_click_file_entry, page_entry)

                directory_entry_icons[page_entry] = page_entry_icon

                if directory in directory_download_files:
                    directory_download_files[directory].append(page_entry)
                else:
                    directory_download_files[directory] = [page_entry]

                page_entry_row = flet.Row(controls = [page_entry_icon, page_entry_text])
                page_entry_rows.append(page_entry_row)

            page_view = flet.ListView(controls = page_entry_rows)
            pages.append(page_view)

        pages_view = flet.PageView(controls = pages, height = 220)
        
        directory_pages[directory] = pages_view
        directory_name_text = f"{directory.filename} ({relevant_api_key})"

        if parent_directory:
            to_parent_directory_button = flet.TextButton(directory_name_text)
            to_parent_directory_button.on_click = partial(go_to_page_entry_directory, parent_directory, download_directory_set)

            directory_names[directory] = to_parent_directory_button
        else:
            directory_names[directory] = flet.Text(directory_name_text)

    def make_directory_data(api_key: str, download_directory_set: bool):
        neocities_list_info = neocities_api_list(api_key = api_key)

        neocities_files = neocities_list_info.directory_entries
        neocities_files_directory_lookup = neocities_list_info.directory_lookup

        for (neocities_directory, neocities_directory_files) in neocities_files.items():
            parent_uuid = neocities_directory.parent_uuid
            parent_directory = neocities_files_directory_lookup[parent_uuid] if parent_uuid else None

            make_directory_displays(directory = neocities_directory, parent_directory = parent_directory, directory_entries = neocities_directory_files, relevant_api_key = api_key, download_directory_set = download_directory_set)

        set_download_button()

    def on_click_toggle_all_none(e: flet.Event[flet.TextButton]):
        toggle_all = toggle_all_none_button.content == SELECT_ALL_BUTTON_TEXT
        
        for download_files in directory_download_files.values():
            for download_file in download_files:
                download_file_icon = directory_entry_icons[download_file]

                if isinstance(download_file, NeocitiesDirectoryEntry):
                    if toggle_all and download_file_icon.icon != FILE_ICON_DOWNLOAD:
                        download_file_icon.icon = FILE_ICON_DOWNLOAD
                    elif not toggle_all and download_file_icon.icon != FILE_ICON_NO_DOWNLOAD:
                        download_file_icon.icon = FILE_ICON_NO_DOWNLOAD
                elif isinstance(download_file, NeocitiesDirectory):
                    if toggle_all and download_file_icon.icon != DIRECTORY_ICON_DOWNLOAD:
                        download_file_icon.icon = DIRECTORY_ICON_DOWNLOAD
                    elif not toggle_all and download_file_icon.icon != DIRECTORY_ICON_NO_DOWNLOAD:
                        download_file_icon.icon = DIRECTORY_ICON_NO_DOWNLOAD

        if toggle_all_none_button.content == SELECT_ALL_BUTTON_TEXT:
            toggle_all_none_button.content = DESELECT_ALL_BUTTON_TEXT
            buttons_row.offset = DOWNLOAD_BUTTONS_DESELECT_ALL_VISIBLE_OFFSET
        elif toggle_all_none_button.content == DESELECT_ALL_BUTTON_TEXT:
            toggle_all_none_button.content = SELECT_ALL_BUTTON_TEXT
            buttons_row.offset = DOWNLOAD_BUTTONS_SELECT_ALL_VISIBLE_OFFSET

        set_download_button()

    toggle_all_none_button.on_click = on_click_toggle_all_none

    if os.path.exists(settings_file_path):
        settings_file_config.read(settings_file_path)
        default_settings = settings_file_config[SETTINGS_FILE_DEFAULT]

        download_directory_set = SETTINGS_FILE_DOWNLOAD_DIRECTORY in default_settings

        if SETTINGS_FILE_API_KEY in default_settings:
            next_page_button.visible = True
            previous_page_button.visible = True
            
            if download_directory_set:
                download_button.visible = True
                
                toggle_all_none_button.visible = True
                toggle_all_none_button.content = DESELECT_ALL_BUTTON_TEXT
    
                buttons_row.offset = DOWNLOAD_BUTTONS_DESELECT_ALL_VISIBLE_OFFSET
            else:
                buttons_row.offset = DOWNLOAD_BUTTONS_NO_TEXT_VISIBLE_OFFSET

            settings_file_api_key = default_settings[SETTINGS_FILE_API_KEY]
            make_directory_data(api_key = settings_file_api_key, download_directory_set = download_directory_set)

            root_pages = directory_pages[NEOCITIES_LIST_ROOT]

            display_column.controls = [directory_names[NEOCITIES_LIST_ROOT], root_pages]

            set_up_navigation_buttons(page_view = root_pages)
            if download_directory_set:
                set_up_download_button(page_directory = NEOCITIES_LIST_ROOT)

        settings_button.on_click = partial(settings_button_clicked, NEOCITIES_LIST_ROOT)
    else:
        settings_button.on_click = partial(settings_button_clicked, NEOCITIES_LIST_ROOT)

    settings_api_key = flet.TextField(width = 400, height = 50, margin = flet.Margin(left = 80, top = 30), label = "API Key")
    settings_api_key.error_style = flet.TextStyle(height = 1.05)

    settings_api_key_input = ""
    
    async def on_finished_typing_api_key(e: flet.Event[flet.TextField]):
        settings_api_key_value = settings_api_key.value

        # Verify API key validity with the most inexpensive API call possible.
        if neocities_api_info(api_key = settings_api_key_value).ok:
            settings_api_key_input = settings_api_key_value

            if settings_api_key.error:
                settings_api_key.error = None

            default_config = settings_file_config[SETTINGS_FILE_DEFAULT]
            default_config[SETTINGS_FILE_API_KEY] = settings_api_key_input

            with open(settings_file_path, "w") as settings_file:
                settings_file_config.write(settings_file)

            download_directory_set = SETTINGS_FILE_DOWNLOAD_DIRECTORY in default_config
            make_directory_data(api_key = settings_api_key_input, download_directory_set = download_directory_set)

            root_pages = directory_pages[NEOCITIES_LIST_ROOT]
            set_up_navigation_buttons(page_view = root_pages)

            if download_directory_set:
                set_up_download_button(page_directory = NEOCITIES_LIST_ROOT)

            settings_button.on_click = partial(settings_button_clicked, NEOCITIES_LIST_ROOT)

            toggle_all_none_button.content = DESELECT_ALL_BUTTON_TEXT
        else:
            settings_api_key.error = "Invalid API Key"

    settings_api_key.on_blur = on_finished_typing_api_key

    settings_download_directory = flet.TextField(width = 375, height = 50, margin = flet.Margin(left = 80, top = 30), label = "Download directory", read_only = True)

    settings_download_directory_button.on_click = partial(handle_picking_download_directory, None)

    settings_download_directory_row = flet.Row(controls = [settings_download_directory, settings_download_directory_button])

    page.title = GUI_TITLE

    page.window.width = GUI_WIDTH
    page.window.height = GUI_HEIGHT

    page.window.maximizable = False

    content = flet.Column(controls = [tabs, display_column, buttons_row])

    page.add(
        flet.SafeArea(
            content = content
        )
    )

if __name__ == "__main__":
    flet.run(main)