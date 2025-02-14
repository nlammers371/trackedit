import napari
import pandas as pd

from motile_tracker.application_menus.editing_menu import EditingMenu
from motile_tracker.data_views import TracksViewer, TreeWidget   
from motile_tracker.data_model.solution_tracks import SolutionTracks

from qtpy.QtWidgets import (
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QLineEdit,
)
from PyQt5.QtCore import Qt
from qtpy.QtCore import Signal
from trackedit.DatabaseHandler import DatabaseHandler

class TrackEditSidebar(QWidget):

    change_chunk = Signal(str)
    goto_frame = Signal(int)

    def __init__(self, viewer: napari.Viewer):
        super().__init__()

        self.tracks_viewer = TracksViewer.get_instance(viewer)

        #Define the buttons
        self.time_prev_btn = QPushButton("prev (<)")
        self.time_prev_btn.clicked.connect(self.press_prev)
        self.time_next_btn = QPushButton("next (>)")
        self.time_next_btn.clicked.connect(self.press_next)
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.time_prev_btn)
        button_layout.addWidget(self.time_next_btn)

        #Define the time window label
        self.chunk_label = QLabel("temp. label")

        # Define an input field that shows the current time frame
        # and allows the user to type a new frame number.
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("Enter time")
        self.time_input.returnPressed.connect(self.on_time_input_entered)


        label_layout = QVBoxLayout()
        label_layout.addWidget(self.chunk_label, alignment=Qt.AlignCenter)
        label_layout.addWidget(self.time_input, alignment=Qt.AlignCenter)

        #Define entire widget
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel(r"""<h2>Navigation</h2>""" ))
        main_layout.addLayout(label_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.setMaximumHeight(150)

    def press_prev(self):
        self.change_chunk.emit('prev')
        # self.update_label()

    def press_next(self):
        self.change_chunk.emit('next')
        # self.update_label()

    def on_time_input_entered(self):
        """Called when the user presses Enter in the time_input field."""
        try:
            frame = int(self.time_input.text())
            print('frame entered:',frame)
            self.goto_frame.emit(frame)
        except ValueError:
            # If conversion fails, you might want to notify the user.
            # For now, we simply refresh the field to the current time.
            self.update_label()
        pass


    def update_label(self):
        time_window = self.tracks_viewer.tracks.segmentation.time_window
        label = f"time window ({time_window[0]} : {time_window[1]-1})"
        self.chunk_label.setText(label)
    
# overwrite EditingMenu to make sure outlines of points in TreePlot are transparent
class CustomEditingMenu(EditingMenu):
    def __init__(self, viewer: napari.Viewer):
        super().__init__(viewer)  # Call the original init method

        # Create the label
        nav_label = QLabel(r"""<h2>Edit tracks</h2>""")

        # Get the existing layout
        layout = self.layout()  # This retrieves the QVBoxLayout from EditingMenu

        # Insert the label at the beginning
        layout.insertWidget(0, nav_label)

class TrackEditClass():
    def __init__(self, viewer: napari.Viewer, databasehandler: DatabaseHandler):
        self.viewer = viewer

        self.TreeWidget = TreeWidget(self.viewer)
        self.TrackEditSidebar = TrackEditSidebar(self.viewer)
        self.EditingMenu = CustomEditingMenu(self.viewer)

        self.viewer.window.add_dock_widget(self.TreeWidget, area="bottom",name="TreeWidget")
        self.viewer.window.add_dock_widget(self.TrackEditSidebar, area='right', name='TrackEditSidebar')
        self.viewer.window.add_dock_widget(self.EditingMenu,area="right",name="EditingMenu")

        #Todo: provide entire DB_handler
        self.databasehandler = databasehandler
        self.TrackEditSidebar.change_chunk.connect(self.update_chunk)
        self.TrackEditSidebar.goto_frame.connect(self.update_chunk_from_frame)

        self.add_tracks()

    def add_tracks(self):
        """Add a solution set of tracks to the tracks viewer results list

        Args:
            tracker (ultrack.Tracker): the ultrack tracker containing the solution
            name (str): the display name of the solution tracks
        """

        # create tracks object
        tracks = SolutionTracks(
            graph = self.databasehandler.nxgraph,
            segmentation = self.databasehandler.segments,
            pos_attr=("z","y", "x"),
            time_attr="t",
            scale = [1,4,1,1],
        )

        # add tracks to viewer
        tracksviewer = TracksViewer.get_instance(self.viewer)
        tracksviewer.tracks_list.add_tracks(tracks,name=self.databasehandler.name)
        self.viewer.layers.selection.active = self.viewer.layers[self.databasehandler.name+'_seg']   #select segmentation layer

        #update label in TrackEditSidebar
        self.TrackEditSidebar.update_label()

        self.check_button_validity()

        #ToDo: check if all tracks are added or overwritten
    

    def update_chunk(self, direction: str):
        cur_chunk = self.databasehandler.time_chunk

        #change the time chunk index
        if direction == 'prev':
            new_chunk = cur_chunk - 1
        elif direction == 'next':
            new_chunk = cur_chunk + 1

        #check if the new chunk is within the limits
        if new_chunk < 0:
            new_chunk = 0
        elif new_chunk == self.databasehandler.num_time_chunks:
            new_chunk = self.databasehandler.num_time_chunks - 1

        self.databasehandler.set_time_chunk(new_chunk)
        self.add_tracks()

    def update_chunk_from_frame(self, frame: int):
        """Handle navigation by a user-entered time frame.
        
        This calculates the chunk containing the given frame.
        For example, if each chunk is 100 frames, frame 235 belongs in chunk 2.
        """
        print('update chunk from frame:',frame)
        # chunk_size = self.databasehandler.time_chunk_length  # adjust if your chunk size differs
        # new_chunk = frame // chunk_size
        new_chunk = self.databasehandler.find_chunk_from_frame(frame)

        if new_chunk < 0:
            new_chunk = 0
        elif new_chunk >= self.databasehandler.num_time_chunks:
            new_chunk = self.databasehandler.num_time_chunks - 1

        # cur_frame = self.viewer.dims.current_step[0]
        # cur_world_time = cur_frame + self.databasehandler.time_chunk_starts[new_chunk]

        print('new_chunk:',new_chunk)

        self.databasehandler.set_time_chunk(new_chunk)
        # self.TrackEditSidebar.time_input.setText(str('cur_world_time'))
        self.add_tracks()


    def check_button_validity(self):
        #enable/disable buttons if on first/last chunk
        chunk = self.databasehandler.time_chunk
        if chunk == 0:
            self.TrackEditSidebar.time_prev_btn.setEnabled(False)
        else:
            self.TrackEditSidebar.time_prev_btn.setEnabled(True)

        if chunk == self.databasehandler.num_time_chunks - 1:
            self.TrackEditSidebar.time_next_btn.setEnabled(False)
        else:
            self.TrackEditSidebar.time_next_btn.setEnabled(True)

