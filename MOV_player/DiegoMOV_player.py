import os
import base64
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import vlc
import locale

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class VideoPlayer:
    def __init__(self, root, initial_file=None, language='ja'):
        self.root = root
        self.language = language
        self.translations = self.load_translations(language)
        self.root.title(self.translations['app_title'])
        
        # Set the application icon
        data = """
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
        """
        self.root.tk.call('wm', 'iconphoto', root._w, tk.PhotoImage(data=data))


        # VLC player instance
        vlc_lib_path = resource_path(os.path.join('Frameworks', 'VLC.framework', 'Versions', 'Current', 'lib'))
        os.environ['DYLD_LIBRARY_PATH'] = vlc_lib_path
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()

        # Variables
        self.media_list = []
        self.current_index = 0
        self.is_paused = False
        self.playback_speeds = [1, 1.25, 1.5, 1.75, 2, 2.5 , 3, 4, 5]
        self.current_speed = tk.DoubleVar(value=1.0)

        # Filename label
        self.filename_label = tk.Label(self.root, text=self.translations['no_file_selected'], anchor='center')
        self.filename_label.pack(pady=5)

        # Video panel
        self.video_panel = tk.Frame(self.root)
        self.video_panel.pack(fill=tk.BOTH, expand=1)

        # Control panel
        self.controls = tk.Frame(self.root)
        self.controls.pack(pady=10)

        # Previous button
        self.prev_button = tk.Button(self.controls, text=self.translations['previous'], command=self.previous_video, width=12, height=2)
        self.prev_button.pack(side=tk.LEFT, padx=5)

        # Play/Pause button
        self.play_button = tk.Button(self.controls, text=self.translations['play'], command=self.play_pause, width=12, height=2)
        self.play_button.pack(side=tk.LEFT, padx=5)

        # Stop button
        self.stop_button = tk.Button(self.controls, text=self.translations['stop'], command=self.stop, width=12, height=2)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Next button
        self.next_button = tk.Button(self.controls, text=self.translations['next'], command=self.next_video, width=12, height=2)
        self.next_button.pack(side=tk.LEFT, padx=5)

        # Open button
        self.open_button = tk.Button(self.controls, text=self.translations['open_file'], command=self.open_file, width=12, height=2)
        self.open_button.pack(side=tk.LEFT, padx=5)

        # Speed control
        self.speed_label = tk.Label(self.controls, text=self.translations['speed'] + ":", width=8)
        self.speed_label.pack(side=tk.LEFT, padx=5)

        self.speed_menu = ttk.Combobox(self.controls, textvariable=self.current_speed, values=self.playback_speeds, width=5)
        self.speed_menu.pack(side=tk.LEFT)
        self.speed_menu.bind("<<ComboboxSelected>>", self.change_speed)
        self.speed_menu.current(0)  # Set default speed to 1

        # Embed the video player
        self.root.update_idletasks()  # Ensure the video panel exists
        self.embed_video()

        # Keyboard bindings
        self.root.bind('<Left>', self.on_left_arrow)
        self.root.bind('<Right>', self.on_right_arrow)
        self.root.bind('<space>', self.on_spacebar)

        # If an initial file is provided, play it
        if initial_file:
            if os.path.isfile(initial_file):
                self.open_initial_file(initial_file)
            else:
                messagebox.showerror(self.translations['error_title'], self.translations['file_not_found'].format(initial_file))

    def load_translations(self, language):
        # Define translations within the code
        translations = {
            'app_title': '',
            'no_file_selected': '',
            'previous': '',
            'play': '',
            'pause': '',
            'stop': '',
            'next': '',
            'open_file': '',
            'speed': '',
            'error_title': '',
            'file_not_found': '',
            'no_videos_found': '',
            'change_speed_error': '',
            'play_error': ''
        }

        if language == 'ja':  # Japanese
            translations.update({
                'app_title': 'DiegoMOV プレーヤー',
                'no_file_selected': 'ファイルが選択されていません',
                'previous': '⏮ 前へ',
                'play': '再生',
                'pause': '一時停止',
                'stop': '停止',
                'next': '次へ ⏭',
                'open_file': 'ファイルを開く',
                'speed': '速度',
                'error_title': 'エラー',
                'file_not_found': 'ファイル "{}" が存在しません。',
                'no_videos_found': '選択されたディレクトリにビデオファイルが見つかりませんでした。',
                'change_speed_error': '速度を変更中にエラーが発生しました:\n{}',
                'play_error': 'ビデオ再生中にエラーが発生しました:\n{}'
            })
        else:
            # Default to Japanese if language is not recognized
            translations.update({
                'app_title': 'DiegoMOV プレーヤー',
                'no_file_selected': 'ファイルが選択されていません',
                'previous': '⏮ 前へ',
                'play': '再生',
                'pause': '一時停止',
                'stop': '停止',
                'next': '次へ ⏭',
                'open_file': 'ファイルを開く',
                'speed': '速度',
                'error_title': 'エラー',
                'file_not_found': 'ファイル "{}" が存在しません。',
                'no_videos_found': '選択されたディレクトリにビデオファイルが見つかりませんでした。',
                'change_speed_error': '速度を変更中にエラーが発生しました:\n{}',
                'play_error': 'ビデオ再生中にエラーが発生しました:\n{}'
            })

        return translations

    def embed_video(self):
        if sys.platform.startswith('win'):
            self.player.set_hwnd(self.video_panel.winfo_id())
        elif sys.platform == "darwin":
            # For macOS
            from ctypes import c_void_p
            self.player.set_nsobject(c_void_p(self.video_panel.winfo_id()))
        else:
            self.player.set_xwindow(self.video_panel.winfo_id())

    def open_file(self):
        filetypes = (("Video files", "*.mov;*.mp4;*.avi;*.mkv"), ("All files", "*.*"))
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            folder = os.path.dirname(filepath)
            # Get all video files in the folder
            video_extensions = ('.mov', '.mp4', '.avi', '.mkv')
            self.media_list = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(video_extensions)]
            self.media_list.sort()
            if not self.media_list:
                messagebox.showerror(self.translations['error_title'], self.translations['no_videos_found'])
                return
            # Find the index of the selected file
            filename = os.path.basename(filepath)
            try:
                self.current_index = self.media_list.index(os.path.join(folder, filename))
            except ValueError:
                self.current_index = 0  # If not found, default to the first video
            self.play_video(self.media_list[self.current_index])

    def open_initial_file(self, filepath):
        folder = os.path.dirname(filepath)
        # Get all video files in the folder
        video_extensions = ('.mov', '.mp4', '.avi', '.mkv')
        self.media_list = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(video_extensions)]
        self.media_list.sort()
        if not self.media_list:
            messagebox.showerror(self.translations['error_title'], self.translations['no_videos_found'])
            return
        # Find the index of the selected file
        filename = os.path.basename(filepath)
        try:
            self.current_index = self.media_list.index(os.path.join(folder, filename))
        except ValueError:
            self.current_index = 0  # If not found, default to the first video
        self.play_video(self.media_list[self.current_index])

    def play_video(self, path):
        try:
            media = self.instance.media_new(path)
            self.player.set_media(media)
            self.embed_video()
            self.player.play()
            self.play_button.config(text=self.translations['pause'])
            self.is_paused = False
            # Display the filename
            filename = os.path.basename(path)
            self.filename_label.config(text=filename)
            # Set playback speed
            self.change_speed()
            # Maximize the window to fill the screen
            self.root.state('zoomed')  # For Windows
            # For other platforms, you might need to use different methods
            # Example for Linux:
            # self.root.attributes('-zoomed', True)
            # Example for macOS:
            # self.root.attributes('-fullscreen', True)
        except Exception as e:
            messagebox.showerror(self.translations['error_title'], self.translations['play_error'].format(e))

    def play_pause(self, event=None):
        if self.player.is_playing():
            self.player.pause()
            self.play_button.config(text=self.translations['play'])
            self.is_paused = True
        else:
            self.player.play()
            self.play_button.config(text=self.translations['pause'])
            self.is_paused = False
            # Ensure the playback speed is set when resuming
            self.change_speed()

    def stop(self):
        self.player.stop()
        self.play_button.config(text=self.translations['play'])
        self.is_paused = False

    def next_video(self, event=None):
        if not self.media_list:
            return
        self.current_index = (self.current_index + 1) % len(self.media_list)
        self.play_video(self.media_list[self.current_index])

    def previous_video(self, event=None):
        if not self.media_list:
            return
        self.current_index = (self.current_index - 1) % len(self.media_list)
        self.play_video(self.media_list[self.current_index])

    def change_speed(self, event=None):
        speed = self.current_speed.get()
        try:
            self.player.set_rate(float(speed))
        except Exception as e:
            messagebox.showerror(self.translations['error_title'], self.translations['change_speed_error'].format(e))

    def on_left_arrow(self, event):
        self.previous_video()

    def on_right_arrow(self, event):
        self.next_video()

    def on_spacebar(self, event):
        self.play_pause()

    def on_closing(self):
        self.player.stop()
        self.root.destroy()

def get_system_language():
    lang, _ = locale.getdefaultlocale()
    if lang and lang.startswith('ja'):
        return 'ja'
    else:
        # Default to Japanese if language is not recognized
        return 'ja'

if __name__ == "__main__":
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    root.geometry("800x600")
    
    player = VideoPlayer(root, initial_file=initial_file, language='ja')
    root.protocol("WM_DELETE_WINDOW", player.on_closing)

    root.mainloop()
