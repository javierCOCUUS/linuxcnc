class MachinePostProcessor:
    def __init__(self):
        self.name = "3 spindles (mm) (*.tap)"
        self.extension = "tap"
        self.units = "MM"
        self.line_ending = "\r\n"
        
    def header(self, tool_number, spindle_speed, x_home=0, y_home=0, z_home=10):
        lines = [
            "G90",
            f"T{tool_number}M6",
            "G17",
            "(WCS by M6Start: G54/G55/G56/G57)",
            f"G0X{x_home:.3f}Y{y_home:.3f}",
            f"G43 H{tool_number} Z{z_home:.3f}",
            f"S{spindle_speed}M3"
        ]
        return self.line_ending.join(lines) + self.line_ending

    def tool_change(self, tool_number, spindle_speed, x_home=0, y_home=0, z_home=10):
        lines = [
            "M5",
            "G49",
            "G90",
            f"T{tool_number}M6",
            "(WCS by M6Start: G54/G55/G56/G57)",
            f"G0X{x_home:.3f}Y{y_home:.3f}",
            f"G43 H{tool_number} Z{z_home:.3f}",
            f"S{spindle_speed}M03"
        ]
        return self.line_ending.join(lines) + self.line_ending

    def rapid_move(self, x=None, y=None, z=None):
        cmd = "G0"
        if x is not None: cmd += f"X{x:.3f}"
        if y is not None: cmd += f"Y{y:.3f}"
        if z is not None: cmd += f"Z{z:.3f}"
        return cmd + self.line_ending

    def first_feed_move(self, x=None, y=None, z=None, feed_rate=None):
        cmd = "G1"
        if x is not None: cmd += f"X{x:.3f}"
        if y is not None: cmd += f"Y{y:.3f}"
        if z is not None: cmd += f"Z{z:.3f}"
        if feed_rate is not None: cmd += f"F{feed_rate:.1f}"
        return cmd + self.line_ending

    def feed_move(self, x=None, y=None, z=None):
        cmd = ""
        if x is not None: cmd += f"X{x:.3f}"
        if y is not None: cmd += f"Y{y:.3f}"
        if z is not None: cmd += f"Z{z:.3f}"
        return cmd + self.line_ending

    def footer(self, x_home=0, y_home=0, z_home=10):
        lines = [
            f"G0Z{z_home:.3f}",
            f"G0X{x_home:.3f}Y{y_home:.3f}",
            "M30"
        ]
        return self.line_ending.join(lines) + self.line_ending
