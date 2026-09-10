"""Token stream filter."""

class StreamTextFilter:
    def __init__(self):
        self.buffer = ""
        self.in_xml = False
        self.xml_buffer = ""

    def feed(self, delta: str) -> list[str]:
        # Handle XML function tag filtering
        if self.in_xml:
            self.xml_buffer += delta
            # Look for closing tag
            end_idx = self.xml_buffer.find("</function>")
            if end_idx != -1:
                self.in_xml = False
                trailing = self.xml_buffer[end_idx + len("</function>"):]
                self.xml_buffer = ""
                return self.feed(trailing)
            return []
        
        text = self.buffer + delta
        self.buffer = ""
        
        start_idx = text.find("<function=")
        if start_idx != -1:
            pre_text = text[:start_idx]
            self.in_xml = True
            self.xml_buffer = text[start_idx:]
            return [pre_text] if pre_text else []
        
        # Check for partial prefix
        for length in range(1, 10):
            suffix = text[-length:]
            if "<function=".startswith(suffix):
                self.buffer = suffix
                main_text = text[:-length]
                return [main_text] if main_text else []
                
        return [text] if text else []

    def flush(self) -> list[str]:
        results = []
        if self.buffer:
            results.append(self.buffer)
            self.buffer = ""
            
        if self.xml_buffer:
            results.append(self.xml_buffer)
            self.xml_buffer = ""
            
        return results

