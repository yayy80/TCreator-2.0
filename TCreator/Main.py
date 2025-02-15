#!/usr/bin/env python3
"""
Improved TCreator Application

This application uses Tkinter to create a mod creation workspace.
It loads mod settings, lists existing items/tiles, and allows
creation/editing via a more modular and object-oriented structure.
"""

import os
import re
from math import *
from random import *
from tkinter import (
    Tk, Frame, Button, Label, Canvas, Scrollbar, Listbox,
    Spinbox, Checkbutton, BooleanVar, IntVar, StringVar, END, FLAT, BOTH, RIGHT, LEFT, Y, ACTIVE
)
from tkinter import simpledialog
from PIL import Image
from functools import partial

# --- Constants and Enums --- #
class FileTypes:
    TILE = 0
    ITEM = 1
    NPC = 2
    PROJECTILE = 3
    DUST = 4
    BUFF = 5


# --- Utility Functions --- #
def get_image_dimensions(image_path, width=True, height=True):
    """Return image dimensions (or defaults) using PIL."""
    try:
        with Image.open(image_path) as img:
            awidth, aheight = img.size
    except OSError as e:
        print(f"Unable to open image file: {e}")
        awidth, aheight = 16, 16

    if width and height:
        return awidth, aheight
    elif width:
        return awidth
    elif height:
        return aheight
    else:
        return awidth, aheight


def extract_number_from_string(string):
    """Extract the first number found in the given string."""
    match = re.search(r"\d+", string)
    return int(match.group(0)) if match else None


def list_files_with_extension(directory, extension):
    """Return a list of file names (without extension) with the given extension in a directory."""
    if not os.path.exists(directory):
        return []
    return [file[:-len(extension)] for file in os.listdir(directory) if file.endswith(extension)]


def list_folders(path):
    """Return a list of folder names in a given path."""
    return [item for item in os.listdir(path) if os.path.isdir(os.path.join(path, item))]


def read_file_lines(filepath):
    """Read file lines or return empty list if file not found."""
    try:
        with open(filepath, 'r') as f:
            return f.readlines()
    except IOError as e:
        print(f"Error reading {filepath}: {e}")
        return []


def get_replaced_values(file_path, file_type):
    """
    Given a file path and file type, extract and return a dictionary of values
    for later template replacement.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()
    except IOError as e:
        print(f"Error opening {file_path}: {e}")
        return {}

    replaced_values = {}

    if file_type == FileTypes.ITEM:
        patternV = r'(\w+)\s+=\s+(.*?);'
        matchesV = re.findall(patternV, content)
        patternC = r'(?:Item|Tile)\.\w+\s+=\s+(.*?);'
        matchesC = re.findall(patternC, content)
        # Optionally extract a tile placement pattern
        patternPlaceable = r'Item\.DefaultToPlaceableTile\(ModContent\.TileType<Tiles\.(\w+)>'
        matchPlaceable = re.search(patternPlaceable, content)

        for (key, _), value in zip(matchesV, matchesC):
            replaced_values[f"<{key.upper()}>"] = value

    elif file_type == FileTypes.TILE:
        # Patterns for tile properties
        patterns = {
            'solid': r'Main\.tileSolid\[Type\]\s+=\s+(.*?);',
            'merge_dirt': r'Main\.tileMergeDirt\[Type\]\s+=\s+(.*?);',
            'block_light': r'Main\.tileBlockLight\[Type\]\s+=\s+(.*?);',
            'dust_type': r'DustType\s+=\s+(.*?);',
            'map_entry': r'AddMapEntry\(new Color\((.*?)\)\);'
        }
        match_solid = re.search(patterns['solid'], content)
        match_merge = re.search(patterns['merge_dirt'], content)
        match_block = re.search(patterns['block_light'], content)
        match_dust = re.search(patterns['dust_type'], content)
        match_map = re.search(patterns['map_entry'], content)

        if match_map:
            colors = match_map.group(1).split(',')
            if len(colors) >= 3:
                map_color_r, map_color_g, map_color_b = colors[:3]
            else:
                map_color_r = map_color_g = map_color_b = None
        else:
            map_color_r = map_color_g = map_color_b = None

        replaced_values = {
            'solid': match_solid.group(1) if match_solid else None,
            'merge_dirt': match_merge.group(1) if match_merge else None,
            'block_light': match_block.group(1) if match_block else None,
            'dust_type': match_dust.group(1) if match_dust else None,
            'map_color_r': map_color_r,
            'map_color_g': map_color_g,
            'map_color_b': map_color_b
        }

    return replaced_values


def create_file_from_template(template_path, new_file_path, replacements, currentpath, currentmod):
    """Read a template file, perform replacements, and save the new file."""
    try:
        with open(template_path, 'r') as template_file:
            template_content = template_file.read()
    except IOError as e:
        print(f"Error reading template {template_path}: {e}")
        return

    # Replace keys in the template content
    for key, value in replacements.items():
        # For dynamic values, if value is callable, call it
        if callable(value):
            replace = value()
        else:
            replace = str(value)
        template_content = template_content.replace(key, replace)

    # Ensure directory exists
    os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
    try:
        with open(new_file_path, 'w') as new_file:
            new_file.write(template_content)
        print(f"Created file: {new_file_path}")
    except IOError as e:
        print(f"Error writing file {new_file_path}: {e}")

    # Open workspace after saving (if desired)
    # For example: app.open_workspace(currentpath, currentmod)


# --- Data Classes --- #
class ElementData:
    def __init__(self, element_type, values, name):
        self.type = element_type
        self.values = values  # A dictionary of properties
        self.name = name


class ElementButton(Button):
    def __init__(self, parent, element_data, accent_color, highlight_color, command, **kwargs):
        self.element_data = element_data
        super().__init__(
            parent,
            text=element_data.name,
            bg=accent_color,
            activebackground=highlight_color,
            command=partial(command, element_data),
            **kwargs
        )


# --- UI Components --- #
class ScrollableWindow(Frame):
    def __init__(self, parent, items, accent_color, highlight_color, button_click_callback, width=300, height=200, bg="white"):
        super().__init__(parent, bg=bg)
        self.accent_color = accent_color
        self.highlight_color = highlight_color
        self.button_click_callback = button_click_callback

        canvas = Canvas(self, bg=bg, relief=FLAT)
        scrollbar = Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        self.inner_frame = Frame(canvas, bg=bg)
        self.inner_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        for item in items:
            btn = ElementButton(
                self.inner_frame, item, accent_color, highlight_color,
                command=self.button_click_callback
            )
            btn.pack(fill="x", expand=True)


# --- Main Application Class --- #
class TCreatorApp:
    def __init__(self):
        # Read colors and settings
        self.main_theme_color = "#FFFFFF"
        self.secondary_theme_color = "#CCCCCC"
        self.accent_color = "#FFAA00"
        self.highlight_color = "#FFD700"
        self.read_colors("colors.TCtheme")
        self.mod_location = self.read_mod_settings("settings.txt")

        # Initialize Tkinter root window
        self.root = Tk()
        self.root.title("TCreator - Start Menu")
        self.root.geometry("1000x600")
        self.root.resizable(False, False)

        self.current_mod_path = ""
        self.current_mod = ""
        self.items = []
        self.tiles = []

        # Frames for navigation and workspace
        self.side_frame = None
        self.main_frame = None

        self.create_main_menu()

    def read_colors(self, filepath):
        lines = read_file_lines(filepath)
        if len(lines) >= 4:
            self.main_theme_color = lines[0].strip()
            self.secondary_theme_color = lines[1].strip()
            self.accent_color = lines[2].strip()
            self.highlight_color = lines[3].strip()
        else:
            print("colors.TCtheme does not contain enough lines; using defaults.")

    def read_mod_settings(self, filepath):
        lines = read_file_lines(filepath)
        if lines:
            mod_location = lines[0].strip()
            print(f"Mod location set to: {mod_location}")
            return mod_location
        return ""

    def create_main_menu(self):
        """Create the main menu UI that lists available mods."""
        # Clear any existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Side frame for mods list and main frame for details
        self.side_frame = Frame(self.root, width=300, height=600, bg=self.secondary_theme_color)
        self.side_frame.grid(row=0, column=0)
        self.main_frame = Frame(self.root, width=700, height=600, bg=self.main_theme_color)
        self.main_frame.grid(row=0, column=1)

        mods = list_folders(self.mod_location)
        btn_y = 2
        for mod in mods:
            btn = Button(
                self.side_frame,
                text=mod,
                height=1,
                width=41,
                bg=self.accent_color,
                activebackground=self.highlight_color,
                command=partial(self.open_workspace, os.path.join(self.mod_location, mod), mod)
            )
            btn.place(x=2, y=btn_y)
            btn_y += 27

    def open_workspace(self, mod_path, mod_name):
        """Set up the workspace for a selected mod."""
        self.current_mod_path = mod_path
        self.current_mod = mod_name

        # Clear the window
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title(f"TCreator - {mod_path}")

        # Load items and tiles
        self.items = list_files_with_extension(os.path.join(mod_path, "Items"), ".cs")
        self.tiles = list_files_with_extension(os.path.join(mod_path, "Tiles"), ".cs")

        # Combine into ElementData objects
        elements = []
        for name in self.items:
            filepath = os.path.join(mod_path, "Items", f"{name}.cs")
            values = get_replaced_values(filepath, FileTypes.ITEM)
            elements.append(ElementData("item", values, name))
        for name in self.tiles:
            filepath = os.path.join(mod_path, "Tiles", f"{name}.cs")
            values = get_replaced_values(filepath, FileTypes.TILE)
            elements.append(ElementData("tile", values, name))

        # Side panel for element list
        self.side_frame = Frame(self.root, width=150, height=600, bg=self.secondary_theme_color)
        self.side_frame.pack(side="left", fill="both")

        # Main panel with scrollable list of elements
        self.main_frame = ScrollableWindow(
            self.root, elements,
            accent_color=self.accent_color,
            highlight_color=self.highlight_color,
            button_click_callback=self.on_element_click,
            bg=self.main_theme_color
        )
        self.main_frame.pack(side="right", fill="both", expand=True)

        # Controls to create a new element
        self.create_new_element_controls()

    def create_new_element_controls(self):
        """Creates UI controls for creating new elements."""
        self.create_list = Listbox(self.root, bg=self.accent_color, selectbackground=self.highlight_color)
        self.create_list.place(x=2, y=2)
        for option in ['item', 'tile', 'npc', 'projectile', 'buff']:
            self.create_list.insert(END, option)

        create_btn = Button(
            self.root,
            bg=self.accent_color,
            activebackground=self.highlight_color,
            text="Create",
            height=1,
            width=16,
            command=self.create_element
        )
        create_btn.place(x=2, y=180)

        main_menu_btn = Button(
            self.root,
            bg=self.accent_color,
            activebackground=self.highlight_color,
            text="Main Menu",
            command=self.create_main_menu
        )
        main_menu_btn.place(x=2, y=552)

    def on_element_click(self, element_data):
        """Callback when an element button is clicked."""
        print(f"Button '{element_data.name}' clicked!")
        for key, value in element_data.values.items():
            print(f"{key} = {value}")

        # Dispatch to the correct creation function based on element type
        if element_data.type == "item":
            self.create_element(element_data)
        elif element_data.type == "tile":
            self.create_element(element_data)
        else:
            print("Not implemented for", element_data.type)

    def create_element(self, element_data=None):
        """
        Create or edit an element.
        If element_data is provided, prefill with the replaced values.
        """
        # Clear current UI (you may choose to open in a new window instead)
        for widget in self.root.winfo_children():
            widget.destroy()

        # Ask for the element name (or use existing name)
        if element_data:
            name = element_data.name
            element_type = element_data.type
            extra_data = element_data.values
        else:
            element_type = self.create_list.get(self.create_list.curselection())
            name = simpledialog.askstring('Text Input', 'Name without spaces:')
            extra_data = None

        # Build a simple form based on type (example shown for "item" and "tile")
        if element_type == "item":
            self.build_item_form(name, extra_data)
        elif element_type == "tile":
            self.build_tile_form(name, extra_data)
        else:
            Label(self.root, text=f"Creation form for '{element_type}' not implemented.").pack()

    def build_item_form(self, name, extra_data):
        """Build the UI form for creating/editing an item."""
        Label(self.root, text=f"Create/Edit Item: {name}", bg=self.main_theme_color).pack(pady=10)

        # Example variables
        use_time = IntVar(value=int(extra_data.get("<USETIME>", 0)) if extra_data else 0)
        damage = IntVar(value=int(extra_data.get("<DAMAGE>", 0)) if extra_data else 0)

        Label(self.root, text="Use Time", bg=self.main_theme_color).pack()
        Spinbox(self.root, from_=0, to=10000, textvariable=use_time, bg=self.accent_color).pack()

        Label(self.root, text="Damage", bg=self.main_theme_color).pack()
        Spinbox(self.root, from_=0, to=10000, textvariable=damage, bg=self.accent_color).pack()

        # More fields can be added similarly...
        # Save button that triggers template file creation.
        save_btn = Button(
            self.root,
            text="Save",
            bg=self.accent_color,
            activebackground=self.highlight_color,
            command=lambda: self.save_template(
                "item", name, {
                    "<NAME>": name,
                    "<USETIME>": lambda: str(use_time.get()),
                    "<DAMAGE>": lambda: str(damage.get()),
                    # Add more key replacements here...
                    "<WIDTH>": lambda: str(get_image_dimensions(os.path.join(self.current_mod_path, "Items", f"{name}.png"), width=True)),
                    "<HEIGHT>": lambda: str(get_image_dimensions(os.path.join(self.current_mod_path, "Items", f"{name}.png"), height=True))
                }
            )
        )
        save_btn.pack(pady=20)

    def build_tile_form(self, name, extra_data):
        """Build the UI form for creating/editing a tile."""
        Label(self.root, text=f"Create/Edit Tile: {name}", bg=self.main_theme_color).pack(pady=10)

        # Example variables
        map_r = IntVar(value=int(extra_data.get("map_color_r", 0)) if extra_data else 0)
        map_g = IntVar(value=int(extra_data.get("map_color_g", 0)) if extra_data else 0)
        map_b = IntVar(value=int(extra_data.get("map_color_b", 0)) if extra_data else 0)

        Label(self.root, text="Map Color R", bg=self.main_theme_color).pack()
        Spinbox(self.root, from_=0, to=255, textvariable=map_r, bg=self.accent_color).pack()

        Label(self.root, text="Map Color G", bg=self.main_theme_color).pack()
        Spinbox(self.root, from_=0, to=255, textvariable=map_g, bg=self.accent_color).pack()

        Label(self.root, text="Map Color B", bg=self.main_theme_color).pack()
        Spinbox(self.root, from_=0, to=255, textvariable=map_b, bg=self.accent_color).pack()

        # More fields can be added here...

        save_btn = Button(
            self.root,
            text="Save",
            bg=self.accent_color,
            activebackground=self.highlight_color,
            command=lambda: self.save_template(
                "tile", name, {
                    "<NAME>": name,
                    "<MAPR>": lambda: str(map_r.get()),
                    "<MAPG>": lambda: str(map_g.get()),
                    "<MAPB>": lambda: str(map_b.get()),
                    "<SOLID>": lambda: "true"  # Example static replacement
                    # Add more key replacements as needed...
                }
            )
        )
        save_btn.pack(pady=20)

    def save_template(self, element_type, name, replacements):
        """
        Create a file from the appropriate template based on the element type.
        The `replacements` argument should be a dict mapping template placeholders to
        either static values or callables returning strings.
        """
        template_path = os.path.join("Templates", f"{element_type}.txt")
        # Save into Items or Tiles folder based on type
        target_folder = os.path.join(self.current_mod_path, f"{element_type.capitalize()}s")
        new_file_path = os.path.join(target_folder, f"{name}.cs")
        create_file_from_template(template_path, new_file_path, replacements, self.current_mod_path, self.current_mod)
        # After saving, return to workspace
        self.open_workspace(self.current_mod_path, self.current_mod)

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = TCreatorApp()
    app.run()
