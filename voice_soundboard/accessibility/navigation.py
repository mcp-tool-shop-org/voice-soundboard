"""
Navigation & Orientation - Landmarks, tables, document structure.

This module provides navigation aids for audio content, helping
users orient themselves and navigate through structured content.

Components:
    AudioLandmarks      - Audio cues for content structure
    TableNavigator      - Accessible table navigation
    DocumentStructure   - Document structure parsing/nav
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class LandmarkType(Enum):
    """Types of content landmarks."""
    HEADING = auto()
    SECTION = auto()
    LIST = auto()
    TABLE = auto()
    FIGURE = auto()
    LINK = auto()
    PARAGRAPH = auto()


@dataclass
class Landmark:
    """A content landmark for navigation.
    
    Attributes:
        type: Type of landmark
        text: Landmark text/label
        level: Level (for headings, lists)
        position: Position in content
    """
    type: LandmarkType
    text: str
    level: int = 1
    position: int = 0


@dataclass
class AudioLandmarksConfig:
    """Configuration for audio landmarks."""
    earcons: dict[LandmarkType, str] = field(default_factory=lambda: {
        LandmarkType.HEADING: "chime_up.wav",
        LandmarkType.SECTION: "section.wav",
        LandmarkType.LIST: "list_start.wav",
        LandmarkType.TABLE: "table.wav",
        LandmarkType.FIGURE: "figure.wav",
        LandmarkType.LINK: "click.wav",
    })
    announce_structure: bool = True
    announce_level: bool = True


class AudioLandmarks:
    """Audio cues for content structure navigation.
    
    Provides earcons and announcements to help users understand
    and navigate document structure.
    
    Example:
        landmarks = AudioLandmarks()
        engine = VoiceEngine(Config(landmarks=landmarks))
        
        # Earcons play at structural boundaries
        # Users can jump between headings, sections, etc.
    """
    
    def __init__(self, config: Optional[AudioLandmarksConfig] = None) -> None:
        """Initialize audio landmarks.
        
        Args:
            config: Landmarks configuration
        """
        self.config = config or AudioLandmarksConfig()
        self._landmarks: list[Landmark] = []
        self._current_index: int = -1
    
    def add_landmark(self, landmark: Landmark) -> None:
        """Add a landmark to the navigation.
        
        Args:
            landmark: Landmark to add
        """
        self._landmarks.append(landmark)
    
    def parse_content(self, content: str) -> list[Landmark]:
        """Parse content to extract landmarks.
        
        Args:
            content: Text content (may be markdown/HTML)
            
        Returns:
            List of extracted landmarks
        """
        landmarks = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Detect headings (markdown)
            if line.startswith('#'):
                level = len(line.split()[0])  # Count #'s
                text = line.lstrip('#').strip()
                landmarks.append(Landmark(
                    type=LandmarkType.HEADING,
                    text=text,
                    level=level,
                    position=i,
                ))
            
            # Detect lists
            elif line.strip().startswith(('-', '*', '1.')):
                landmarks.append(Landmark(
                    type=LandmarkType.LIST,
                    text="List item",
                    position=i,
                ))
        
        self._landmarks = landmarks
        return landmarks
    
    def next_landmark(self, type_filter: Optional[LandmarkType] = None) -> Optional[Landmark]:
        """Navigate to next landmark.
        
        Args:
            type_filter: Only consider this type (None = any)
            
        Returns:
            Next landmark or None
        """
        for i in range(self._current_index + 1, len(self._landmarks)):
            lm = self._landmarks[i]
            if type_filter is None or lm.type == type_filter:
                self._current_index = i
                return lm
        return None
    
    def previous_landmark(self, type_filter: Optional[LandmarkType] = None) -> Optional[Landmark]:
        """Navigate to previous landmark.
        
        Args:
            type_filter: Only consider this type (None = any)
            
        Returns:
            Previous landmark or None
        """
        for i in range(self._current_index - 1, -1, -1):
            lm = self._landmarks[i]
            if type_filter is None or lm.type == type_filter:
                self._current_index = i
                return lm
        return None
    
    def get_earcon(self, landmark: Landmark) -> Optional[str]:
        """Get earcon file for a landmark type.
        
        Args:
            landmark: Landmark to get earcon for
            
        Returns:
            Earcon file path or None
        """
        return self.config.earcons.get(landmark.type)
    
    def announce(self, landmark: Landmark) -> str:
        """Get announcement text for a landmark.
        
        Args:
            landmark: Landmark to announce
            
        Returns:
            Announcement text
        """
        type_names = {
            LandmarkType.HEADING: "Heading",
            LandmarkType.SECTION: "Section",
            LandmarkType.LIST: "List",
            LandmarkType.TABLE: "Table",
            LandmarkType.FIGURE: "Figure",
            LandmarkType.LINK: "Link",
            LandmarkType.PARAGRAPH: "Paragraph",
        }
        
        type_name = type_names.get(landmark.type, "Landmark")
        
        if self.config.announce_level and landmark.level > 0:
            return f"{type_name} level {landmark.level}: {landmark.text}"
        else:
            return f"{type_name}: {landmark.text}"


@dataclass
class TableCell:
    """A cell in a table."""
    row: int
    column: int
    text: str
    is_header: bool = False


@dataclass
class TableNavigatorConfig:
    """Configuration for table navigator."""
    announce_position: bool = True
    announce_headers: bool = True
    wrap_navigation: bool = True
    read_by: str = "row"  # row, column


class TableNavigator:
    """Accessible navigation for tabular data.
    
    Allows users to navigate tables cell-by-cell with
    context announcements (row/column headers).
    
    Example:
        nav = TableNavigator()
        
        table = [
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ]
        
        nav.load(table)
        nav.move_right()  # "Age: 30"
    """
    
    def __init__(self, config: Optional[TableNavigatorConfig] = None) -> None:
        """Initialize table navigator.
        
        Args:
            config: Navigator configuration
        """
        self.config = config or TableNavigatorConfig()
        self._table: list[list[str]] = []
        self._headers: list[str] = []
        self._row_headers: list[str] = []
        self._current_row: int = 0
        self._current_column: int = 0
    
    def load(
        self,
        table: list[list[str]],
        has_header_row: bool = True,
        has_header_column: bool = False,
    ) -> None:
        """Load a table for navigation.
        
        Args:
            table: 2D list of cell values
            has_header_row: First row is headers
            has_header_column: First column is row headers
        """
        self._table = table
        
        if has_header_row and table:
            self._headers = table[0]
            self._current_row = 1 if len(table) > 1 else 0
        else:
            self._headers = []
            self._current_row = 0
        
        if has_header_column and table:
            self._row_headers = [row[0] for row in table]
            self._current_column = 1 if table[0] and len(table[0]) > 1 else 0
        else:
            self._row_headers = []
            self._current_column = 0
    
    @property
    def current_cell(self) -> Optional[str]:
        """Get current cell value."""
        if not self._table:
            return None
        if self._current_row >= len(self._table):
            return None
        if self._current_column >= len(self._table[self._current_row]):
            return None
        return self._table[self._current_row][self._current_column]
    
    @property
    def current_position(self) -> tuple[int, int]:
        """Get current row and column."""
        return (self._current_row, self._current_column)
    
    def move_right(self) -> Optional[str]:
        """Move to next column.
        
        Returns:
            Cell value with context, or None if at edge
        """
        row = self._table[self._current_row] if self._table else []
        
        if self._current_column < len(row) - 1:
            self._current_column += 1
        elif self.config.wrap_navigation:
            self._current_column = 0
        else:
            return None
        
        return self._announce_cell()
    
    def move_left(self) -> Optional[str]:
        """Move to previous column.
        
        Returns:
            Cell value with context, or None if at edge
        """
        if self._current_column > 0:
            self._current_column -= 1
        elif self.config.wrap_navigation:
            row = self._table[self._current_row] if self._table else []
            self._current_column = len(row) - 1
        else:
            return None
        
        return self._announce_cell()
    
    def move_down(self) -> Optional[str]:
        """Move to next row.
        
        Returns:
            Cell value with context, or None if at edge
        """
        if self._current_row < len(self._table) - 1:
            self._current_row += 1
        elif self.config.wrap_navigation:
            self._current_row = 0
        else:
            return None
        
        return self._announce_cell()
    
    def move_up(self) -> Optional[str]:
        """Move to previous row.
        
        Returns:
            Cell value with context, or None if at edge
        """
        if self._current_row > 0:
            self._current_row -= 1
        elif self.config.wrap_navigation:
            self._current_row = len(self._table) - 1
        else:
            return None
        
        return self._announce_cell()
    
    def _announce_cell(self) -> str:
        """Build announcement for current cell."""
        parts = []
        
        if self.config.announce_position:
            parts.append(f"Row {self._current_row + 1}, Column {self._current_column + 1}")
        
        if self.config.announce_headers and self._headers:
            if self._current_column < len(self._headers):
                parts.append(self._headers[self._current_column])
        
        value = self.current_cell or "(empty)"
        parts.append(value)
        
        return ": ".join(parts)
    
    def read_row(self, row: Optional[int] = None) -> str:
        """Read entire row.
        
        Args:
            row: Row index (uses current if None)
            
        Returns:
            Row content as string
        """
        r = row if row is not None else self._current_row
        if r >= len(self._table):
            return ""
        
        cells = self._table[r]
        if self.config.announce_headers and self._headers:
            return ", ".join(
                f"{self._headers[i]}: {cell}"
                for i, cell in enumerate(cells)
                if i < len(self._headers)
            )
        return ", ".join(cells)
    
    def read_column(self, column: Optional[int] = None) -> str:
        """Read entire column.
        
        Args:
            column: Column index (uses current if None)
            
        Returns:
            Column content as string
        """
        c = column if column is not None else self._current_column
        values = [
            row[c] for row in self._table
            if c < len(row)
        ]
        return ", ".join(values)


@dataclass
class Heading:
    """A document heading."""
    level: int
    text: str
    position: int


@dataclass
class Section:
    """A document section."""
    title: str
    content: str
    start: int
    end: int


class DocumentStructure:
    """Parse and navigate document structure.
    
    Extracts headings, sections, and other structural elements
    to enable navigation and table of contents generation.
    
    Example:
        structure = DocumentStructure()
        doc = structure.parse("report.html")
        
        # List headings
        for h in doc.get_headings():
            print(f"{'  ' * h.level}{h.text}")
        
        # Jump to section
        section = doc.get_section("Conclusion")
        engine.speak(section.content)
    """
    
    def __init__(self) -> None:
        """Initialize document structure parser."""
        self._content: str = ""
        self._headings: list[Heading] = []
        self._sections: list[Section] = []
    
    def parse(self, source: str) -> "DocumentStructure":
        """Parse a document from file or string.
        
        Args:
            source: File path or content string
            
        Returns:
            Self for chaining
        """
        # Try to read as file, fall back to treating as content
        try:
            with open(source, 'r', encoding='utf-8') as f:
                self._content = f.read()
        except (FileNotFoundError, OSError):
            self._content = source
        
        self._extract_structure()
        return self
    
    def _extract_structure(self) -> None:
        """Extract headings and sections from content."""
        self._headings = []
        self._sections = []
        
        lines = self._content.split('\n')
        current_section_start = 0
        current_section_title = ""
        
        for i, line in enumerate(lines):
            # Detect markdown headings
            if line.startswith('#'):
                # Save previous section
                if current_section_title:
                    self._sections.append(Section(
                        title=current_section_title,
                        content='\n'.join(lines[current_section_start:i]),
                        start=current_section_start,
                        end=i,
                    ))
                
                level = len(line) - len(line.lstrip('#'))
                text = line.lstrip('#').strip()
                
                self._headings.append(Heading(level=level, text=text, position=i))
                current_section_start = i
                current_section_title = text
        
        # Save final section
        if current_section_title:
            self._sections.append(Section(
                title=current_section_title,
                content='\n'.join(lines[current_section_start:]),
                start=current_section_start,
                end=len(lines),
            ))
    
    def get_headings(self, max_level: int = 6) -> list[Heading]:
        """Get all headings up to a level.
        
        Args:
            max_level: Maximum heading level to include
            
        Returns:
            List of headings
        """
        return [h for h in self._headings if h.level <= max_level]
    
    def get_section(self, title: str) -> Optional[Section]:
        """Get a section by title.
        
        Args:
            title: Section title to find
            
        Returns:
            Section or None if not found
        """
        title_lower = title.lower()
        for section in self._sections:
            if section.title.lower() == title_lower:
                return section
        return None
    
    def generate_toc(self, max_level: int = 3) -> str:
        """Generate table of contents.
        
        Args:
            max_level: Maximum heading level to include
            
        Returns:
            TOC as formatted string
        """
        lines = ["Table of Contents", "=" * 20, ""]
        
        for heading in self.get_headings(max_level):
            indent = "  " * (heading.level - 1)
            lines.append(f"{indent}- {heading.text}")
        
        return "\n".join(lines)
