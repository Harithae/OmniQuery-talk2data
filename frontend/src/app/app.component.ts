import { Component, AfterViewChecked, ElementRef, ViewChildren, QueryList, Pipe, PipeTransform } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { ChatService } from './chat.service';
import { marked } from 'marked';
import { Chart, registerables } from 'chart.js/auto';

Chart.register(...registerables);

@Pipe({
  name: 'markdown',
  standalone: true
})
export class MarkdownPipe implements PipeTransform {
  constructor(private sanitizer: DomSanitizer) { }
  transform(value: string): SafeHtml {
    if (!value) return '';
    const html = marked.parse(value) as string;
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }
}

interface ChartData {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    backgroundColor: string[] | string;
    borderColor: string[] | string;
    borderWidth: number;
    fill?: boolean;
    tension?: number;
  }[];
}

interface Message {
  text: string;
  sender: 'user' | 'agent';
  timestamp: Date;
  hasTable?: boolean;
  showChart?: boolean;
  chartData?: ChartData;
  chartInstance?: Chart | null;
  results?: any;
  showDataTable?: boolean;
<<<<<<< HEAD
  chartType?: 'bar' | 'line' | 'doughnut' | 'horizontalBar';
  chartTotal?: number;
  chartZoom?: number;
  hasMoreRows?: boolean;
  showFullResults?: boolean;
  showTableOptions?: boolean;
  columnWidths?: number[];
=======
  insight?: string;
>>>>>>> main
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownPipe],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements AfterViewChecked {
  title = 'Multi-DB AI Chat';
  userMessage = '';
  messages: Message[] = [
    {
      text: 'Hello! I can help you query the Users and Orders databases. What would you like to know?',
      sender: 'agent',
      timestamp: new Date()
    }
  ];
  isLoading = false;
  currentStatus = '';

  // Column resizing properties
  isResizing = false;
  resizingMessageIndex = -1;
  resizingColumnIndex = -1;
  startX = 0;
  startWidths: number[] = [];

  @ViewChildren('chartCanvas') chartCanvases!: QueryList<ElementRef<HTMLCanvasElement>>;

  constructor(private chatService: ChatService, private sanitizer: DomSanitizer) { }

  ngAfterViewChecked() {
    this.messages.forEach((msg, index) => {
      if (msg.showChart && !msg.chartInstance && msg.chartData) {
        this.initChart(index);
      }
    });
  }

  // Column resizing methods
  initializeColumnWidths(messageIndex: number) {
    const msg = this.messages[messageIndex];
    if (!msg.results || msg.columnWidths) return;

    const columns = this.getColumns(msg.results);
    const tableWidth = 800; // Base table width
    const defaultWidth = tableWidth / columns.length;
    
    msg.columnWidths = columns.map(() => defaultWidth);
  }

  onResizeStart(messageIndex: number, columnIndex: number, event: MouseEvent) {
    event.preventDefault();
    this.isResizing = true;
    this.resizingMessageIndex = messageIndex;
    this.resizingColumnIndex = columnIndex;
    this.startX = event.clientX;
    
    const msg = this.messages[messageIndex];
    this.startWidths = [...(msg.columnWidths || [])];
    
    document.addEventListener('mousemove', this.onResize.bind(this));
    document.addEventListener('mouseup', this.onResizeEnd.bind(this));
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  onResize(event: MouseEvent) {
    if (!this.isResizing) return;
    
    const msg = this.messages[this.resizingMessageIndex];
    if (!msg.columnWidths) return;

    const deltaX = event.clientX - this.startX;
    const minWidth = 80; // Minimum column width
    
    // Update current column width
    const newWidth = Math.max(minWidth, this.startWidths[this.resizingColumnIndex] + deltaX);
    msg.columnWidths[this.resizingColumnIndex] = newWidth;
    
    // Adjust next column width to maintain total width
    if (this.resizingColumnIndex < msg.columnWidths.length - 1) {
      const nextColumnIndex = this.resizingColumnIndex + 1;
      const widthDiff = newWidth - this.startWidths[this.resizingColumnIndex];
      const newNextWidth = Math.max(minWidth, this.startWidths[nextColumnIndex] - widthDiff);
      msg.columnWidths[nextColumnIndex] = newNextWidth;
    }
  }

  onResizeEnd() {
    this.isResizing = false;
    this.resizingMessageIndex = -1;
    this.resizingColumnIndex = -1;
    document.removeEventListener('mousemove', this.onResize.bind(this));
    document.removeEventListener('mouseup', this.onResizeEnd.bind(this));
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }

  getColumnWidth(messageIndex: number, columnIndex: number): string {
    const msg = this.messages[messageIndex];
    if (!msg.columnWidths) {
      this.initializeColumnWidths(messageIndex);
    }
    return msg.columnWidths ? `${msg.columnWidths[columnIndex]}px` : 'auto';
  }



  showTableView(index: number) {
    const msg = this.messages[index];
    
    // Destroy chart if it exists
    if (msg.chartInstance) {
      msg.chartInstance.destroy();
      msg.chartInstance = null;
    }
    
    msg.showChart = false;
    msg.showFullResults = false;
  }

  toggleTableOptions(index: number) {
    const msg = this.messages[index];
    msg.showTableOptions = !msg.showTableOptions;
    msg.showChart = false;
    msg.showFullResults = false;
    
    // Destroy chart instance when switching to table view
    if (msg.chartInstance) {
      msg.chartInstance.destroy();
      msg.chartInstance = null;
    }
  }

  showFullResults(index: number) {
    const msg = this.messages[index];
    
    // Destroy chart if it exists
    if (msg.chartInstance) {
      msg.chartInstance.destroy();
      msg.chartInstance = null;
    }
    
    msg.showChart = false;
    msg.showFullResults = true;
    msg.showTableOptions = false;
  }

  showChartView(index: number) {
    const msg = this.messages[index];
    
    // Reset table options when switching to chart
    msg.showTableOptions = false;
    msg.showFullResults = false;
    
    // Try to parse if not already parsed
    if (!msg.chartData) {
      this.parseTableForChart(index);
    }

    // Only show if we actually have data
    if (msg.chartData && msg.chartData.labels.length > 0) {
      msg.showChart = true;
    } else {
      console.warn('Could not generate chart data for this table');
    }
  }

  parseTableForChart(index: number) {
    const msg = this.messages[index];
    const tokens = marked.lexer(msg.text);

    // Recursive search for table token
    const findTable = (tokenList: any[]): any => {
      for (const t of tokenList) {
        if (t.type === 'table') return t;
        if (t.tokens) {
          const found = findTable(t.tokens);
          if (found) return found;
        }
      }
      return null;
    };

    const tableToken = findTable(tokens);
    if (!tableToken) return;

    const headers = tableToken.header.map((h: any) => h.text);
    const rows = tableToken.rows.map((r: any) => r.map((c: any) => c.text));

    if (rows.length === 0) return;

    // Improved Heuristic: Check all rows to find the best data column
    let labelColIndex = -1;
    let dataColIndex = -1;

    const columnScores = headers.map(() => 0);
    for (const row of rows) {
      row.forEach((cell: string, i: number) => {
        const cleanVal = cell?.replace(/[$,%]/g, '').trim();
        if (cleanVal && !isNaN(parseFloat(cleanVal))) {
          columnScores[i]++;
        }
      });
    }

    // Find the best data column. Prefer right-most columns, and penalize 'ID' columns.
    let bestDataCol = -1;
    for (let i = columnScores.length - 1; i >= 0; i--) {
      if (columnScores[i] > rows.length / 2) {
        const headerLower = (headers[i] || '').toLowerCase();
        const isId = headerLower === 'id' || headerLower.includes(' id') || headerLower.includes('id ') || headerLower === '#';
        if (!isId) {
          bestDataCol = i;
          break;
        }
      }
    }

    if (bestDataCol === -1) {
      // Fallback: just pick any numeric column if no other exists
      bestDataCol = columnScores.findIndex((s: number) => s > rows.length / 2);
    }

    dataColIndex = bestDataCol;

    // Pick first non-numeric column as label
    labelColIndex = columnScores.findIndex((s: number) => s === 0);

    if (dataColIndex === -1) {
      // Last resort: find any column that has at least one number
      dataColIndex = columnScores.findIndex((s: number) => s > 0);
    }

    if (dataColIndex === -1) return; // Still no numeric column
    if (labelColIndex === -1 || labelColIndex === dataColIndex) labelColIndex = 0;

    const labels = rows.map((r: any) => r[labelColIndex]);
    const data = rows.map((r: any) => {
      const cleanVal = r[dataColIndex]?.replace(/[$,%]/g, '').trim();
      return parseFloat(cleanVal) || 0;
    });

    // Calculate total for center display
    const total = data.reduce((sum: number, value: number) => sum + value, 0);
    msg.chartTotal = total;

    const colors = [
      'rgba(99, 102, 241, 0.7)',   // 1. Indigo
      'rgba(14, 165, 233, 0.7)',   // 2. Sky Blue
      'rgba(168, 85, 247, 0.7)',   // 3. Purple
      'rgba(236, 72, 153, 0.7)',   // 4. Pink
      'rgba(249, 115, 22, 0.7)',   // 5. Orange
      'rgba(34, 197, 94, 0.7)',    // 6. Green
      'rgba(239, 68, 68, 0.7)',    // 7. Red
      'rgba(234, 179, 8, 0.7)',    // 8. Yellow
      'rgba(20, 184, 166, 0.7)',   // 9. Teal
      'rgba(217, 70, 239, 0.7)',   // 10. Magenta
      'rgba(251, 146, 60, 0.7)',   // 11. Light Orange
      'rgba(59, 130, 246, 0.7)',   // 12. Blue
      'rgba(139, 92, 246, 0.7)',   // 13. Violet
      'rgba(244, 63, 94, 0.7)',    // 14. Rose
      'rgba(16, 185, 129, 0.7)'    // 15. Emerald
    ];

    msg.chartData = {
      labels,
      datasets: [{
        label: headers[dataColIndex],
        data,
        backgroundColor: labels.map((_: any, i: number) => colors[i % colors.length]),
        borderColor: labels.map((_: any, i: number) => colors[i % colors.length].replace('0.7', '1')),
        borderWidth: 2,
        fill: false // Will be updated dynamically for area charts
      }]
    };
  }

  updateChartDataForType(msg: any, chartType: string) {
    if (!msg.chartData) return;
    
    const dataset = msg.chartData.datasets[0];
    
    if (chartType === 'line') {
      dataset.fill = false;
      dataset.backgroundColor = 'transparent';
      dataset.tension = 0.1;
    } else {
      // Reset to original colors for bar charts
      const colors = [
        'rgba(99, 102, 241, 0.7)',   // 1. Indigo
        'rgba(14, 165, 233, 0.7)',   // 2. Sky Blue
        'rgba(168, 85, 247, 0.7)',   // 3. Purple
        'rgba(236, 72, 153, 0.7)',   // 4. Pink
        'rgba(249, 115, 22, 0.7)',   // 5. Orange
        'rgba(34, 197, 94, 0.7)',    // 6. Green
        'rgba(239, 68, 68, 0.7)',    // 7. Red
        'rgba(234, 179, 8, 0.7)',    // 8. Yellow
        'rgba(20, 184, 166, 0.7)',   // 9. Teal
        'rgba(217, 70, 239, 0.7)',   // 10. Magenta
        'rgba(251, 146, 60, 0.7)',   // 11. Light Orange
        'rgba(59, 130, 246, 0.7)',   // 12. Blue
        'rgba(139, 92, 246, 0.7)',   // 13. Violet
        'rgba(244, 63, 94, 0.7)',    // 14. Rose
        'rgba(16, 185, 129, 0.7)'    // 15. Emerald
      ];
      dataset.backgroundColor = msg.chartData.labels.map((_: any, i: number) => colors[i % colors.length]);
      dataset.borderColor = msg.chartData.labels.map((_: any, i: number) => colors[i % colors.length].replace('0.7', '1'));
      dataset.fill = false;
    }
  }

  changeChartType(index: number, chartType: 'bar' | 'line' | 'doughnut' | 'horizontalBar') {
    const msg = this.messages[index];
    
    // Destroy existing chart instance
    if (msg.chartInstance) {
      msg.chartInstance.destroy();
      msg.chartInstance = null;
    }
    
    msg.chartType = chartType;
    
    // Update chart data for the new type
    this.updateChartDataForType(msg, chartType);
    
    // Use a longer timeout to ensure Angular has updated the view
    setTimeout(() => {
      this.initChart(index);
    }, 50);
  }

  zoomChart(index: number, direction: 'in' | 'out') {
    const msg = this.messages[index];
    if (!msg.chartZoom) msg.chartZoom = 1;
    
    if (direction === 'in') {
      msg.chartZoom = Math.min(msg.chartZoom + 0.2, 3); // Max 3x zoom
    } else {
      msg.chartZoom = Math.max(msg.chartZoom - 0.2, 0.5); // Min 0.5x zoom
    }
    
    // Recreate chart with new zoom
    if (msg.chartInstance) {
      msg.chartInstance.destroy();
      msg.chartInstance = null;
    }
    setTimeout(() => this.initChart(index), 50);
  }

  resetZoom(index: number) {
    const msg = this.messages[index];
    msg.chartZoom = 1;
    
    if (msg.chartInstance) {
      msg.chartInstance.destroy();
      msg.chartInstance = null;
    }
    setTimeout(() => this.initChart(index), 50);
  }

  initChart(index: number) {
    const msg = this.messages[index];
    
    // Find the canvas element by ID
    const canvasElement = document.getElementById(`chart-${index}`) as HTMLCanvasElement;
    
    if (!canvasElement) {
      console.warn(`Canvas element not found for chart-${index}`);
      return;
    }

    if (!msg.chartData) {
      console.warn('No chart data available');
      return;
    }

    // Handle chart type mapping
    let chartType = msg.chartType || 'bar';
    
    // Map custom types to Chart.js types
    if (chartType === 'horizontalBar') {
      chartType = 'bar';
    }

    // Set default zoom if not set
    if (!msg.chartZoom) msg.chartZoom = 1;

    // Dynamic cutout based on text length
    let cutoutPercentage = '70%';
    if (msg.chartTotal !== undefined) {
      const textLength = msg.chartTotal.toString().length;
      if (textLength > 8) {
        cutoutPercentage = '75%'; // Larger hole for long numbers
      } else if (textLength > 6) {
        cutoutPercentage = '72%';
      }
    }

    // Center text plugin for doughnut charts
    const centerTextPlugin = {
      id: 'centerText',
      beforeDraw(chart: any) {
        if (msg.chartType === 'doughnut' && msg.chartTotal !== undefined) {
          const { ctx, chartArea } = chart;
          if (!chartArea) return;
          
          const centerX = (chartArea.left + chartArea.right) / 2;
          const centerY = (chartArea.top + chartArea.bottom) / 2;
          
          ctx.save();
          const text = msg.chartTotal.toString();
          
          let fontSize = 40;
          if (text.length > 8) {
            fontSize = 24;
          } else if (text.length > 6) {
            fontSize = 30;
          } else if (text.length > 4) {
            fontSize = 36;
          }
          
          ctx.font = `bold ${fontSize}px sans-serif`;
          ctx.fillStyle = '#1f2937';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(text, centerX, centerY);
          ctx.restore();
        }
      }
    };

    // External labels plugin for doughnut charts
    const externalLabelsPlugin = {
      id: 'externalLabels',
      afterDraw(chart: any) {
        if (msg.chartType !== 'doughnut') return;
        
        const { ctx, chartArea, data } = chart;
        const centerX = (chartArea.left + chartArea.right) / 2;
        const centerY = (chartArea.top + chartArea.bottom) / 2;
        const radius = Math.min(chartArea.right - centerX, chartArea.bottom - centerY);
        
        ctx.save();
        
        const meta = chart.getDatasetMeta(0);
        const total = data.datasets[0].data.reduce((a: number, b: number) => a + b, 0);
        
        meta.data.forEach((arc: any, index: number) => {
          const label = data.labels[index];
          const value = data.datasets[0].data[index];
          const percentage = ((value / total) * 100).toFixed(2);
          
          // Calculate angle for this segment
          const angle = (arc.startAngle + arc.endAngle) / 2;
          
          // Point on the arc edge
          const x1 = centerX + Math.cos(angle) * (radius * 0.85);
          const y1 = centerY + Math.sin(angle) * (radius * 0.85);
          
          // Extended point for the line
          const lineLength = 30;
          const x2 = centerX + Math.cos(angle) * (radius * 0.85 + lineLength);
          const y2 = centerY + Math.sin(angle) * (radius * 0.85 + lineLength);
          
          // Horizontal line extension
          const horizontalLength = 40;
          const x3 = x2 + (Math.cos(angle) > 0 ? horizontalLength : -horizontalLength);
          const y3 = y2;
          
          // Draw line from arc to label
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.lineTo(x3, y3);
          ctx.strokeStyle = '#64748b';
          ctx.lineWidth = 1;
          ctx.stroke();
          
          // Draw label text
          const text = `${label} - ${percentage}%`;
          ctx.font = '12px sans-serif';
          ctx.fillStyle = '#1e293b';
          ctx.textBaseline = 'middle';
          
          if (Math.cos(angle) > 0) {
            ctx.textAlign = 'left';
            ctx.fillText(text, x3 + 5, y3);
          } else {
            ctx.textAlign = 'right';
            ctx.fillText(text, x3 - 5, y3);
          }
        });
        
        ctx.restore();
      }
    };

    try {
      msg.chartInstance = new Chart(canvasElement, {
        type: chartType as any,
        data: msg.chartData!,
        plugins: msg.chartType === 'doughnut' ? [centerTextPlugin, externalLabelsPlugin] : [],
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: msg.chartType === 'horizontalBar' ? 'y' : 'x',
          cutout: msg.chartType === 'doughnut' ? cutoutPercentage : undefined,
          layout: {
            padding: {
              top: 20,
              bottom: 20,
              left: 20,
              right: 20
            }
          },
          plugins: {
            legend: { 
              display: false
            },
            tooltip: {
              backgroundColor: 'rgba(255, 255, 255, 0.9)',
              titleColor: '#1e293b',
              bodyColor: '#1e293b',
              borderColor: 'rgba(0,0,0,0.1)',
              borderWidth: 1,
              padding: 10,
              displayColors: true
            }
          },
          scales: {
            y: {
              display: msg.chartType !== 'doughnut',
              beginAtZero: true,
              grid: { color: 'rgba(0, 0, 0, 0.05)' },
              ticks: { color: '#64748b', font: { size: 10 } }
            },
            x: {
              display: msg.chartType !== 'doughnut',
              grid: { display: false },
              ticks: { color: '#64748b', font: { size: 10 } }
            }
          }
        }
      });

      // Apply zoom scaling
      if (msg.chartZoom && msg.chartZoom !== 1) {
        canvasElement.style.transform = `scale(${msg.chartZoom})`;
        canvasElement.style.transformOrigin = 'center center';
      } else {
        canvasElement.style.transform = 'scale(1)';
      }
    } catch (error) {
      console.error('Error creating chart:', error);
    }
  }

  async sendMessage() {
    if (!this.userMessage.trim() || this.isLoading) return;

    const messageContent = this.userMessage.trim();
    this.messages.push({
      text: messageContent,
      sender: 'user',
      timestamp: new Date()
    });

    this.userMessage = '';
    this.isLoading = true;
    this.currentStatus = '';

    const agentMessage: Message = {
      text: '',
      sender: 'agent',
      timestamp: new Date(),
      showChart: false,
      showFullResults: false,
      showTableOptions: false,
      chartType: 'bar'
    };
    this.messages.push(agentMessage);

    try {
      const response = await this.chatService.sendMessageStream(messageContent);
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let leftoverBuffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const combinedChunk = leftoverBuffer + chunk;
        const lines = combinedChunk.split('\n');
        leftoverBuffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.type === 'token') {
              agentMessage.text += data.content;
            } else if (data.type === 'insight') {
              agentMessage.insight = (agentMessage.insight || '') + data.content;
            } else if (data.type === 'tool_start') {
              this.currentStatus = `Searching ${data.tool}...`;
            } else if (data.type === 'tool_end') {
              this.currentStatus = '';
            } else if (data.type === 'result') {
              // Store the final result set
              agentMessage.results = data.content;
              // Check if there are more than 10 rows
              agentMessage.hasMoreRows = data.content && data.content.length > 10;
            } else if (data.type === 'error') {
              agentMessage.text = `Error: ${data.content}`;
            }
            this.scrollToBottom();
          } catch (e) { }
        }
      }

      // Clean up the agent message text: remove status messages and "Final Results"
      agentMessage.text = this.cleanAgentMessage(agentMessage.text);

      // After streaming is complete, check for tables more accurately
      const tokens = marked.lexer(agentMessage.text);
      const hasTableToken = (tokenList: any[]): boolean => {
        for (const t of tokenList) {
          if (t.type === 'table') return true;
          if (t.tokens && hasTableToken(t.tokens)) return true;
        }
        return false;
      };

      agentMessage.hasTable = hasTableToken(tokens);

    } catch (err) {
      console.error(err);
      agentMessage.text = 'Sorry, I encountered an error connecting to the server.';
    } finally {
      this.isLoading = false;
      this.currentStatus = '';
      this.scrollToBottom();
    }
  }

  cleanAgentMessage(text: string): string {
    // Remove status messages (✅ Database schemas extracted, etc.)
    text = text.replace(/✅[^\n]*\n?/g, '');
    
    // Replace "Final Results (X rows)" with "Results Summary"
    text = text.replace(/Final Results\s*\(\d+\s*rows?\)/gi, 'Results Summary');
    
    // Remove extra blank lines
    text = text.replace(/\n\n+/g, '\n\n');
    
    return text.trim();
  }



  getColumns(results: any[]): string[] {
    if (!results || results.length === 0) return [];
    const columns = Object.keys(results[0]);
    // Remove underscores, capitalize first letter of each word
    return columns.map(col => 
      col
        .replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ')
    );
  }

  getColumnKey(results: any[], displayName: string): string {
    if (!results || results.length === 0) return displayName;
    const columns = Object.keys(results[0]);
    // Find the original column name that matches the display name
    return columns.find(col => {
      const formatted = col
        .replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
      return formatted === displayName;
    }) || displayName;
  }

  scrollToBottom() {
    setTimeout(() => {
      const chatContainer = document.querySelector('.chat-messages');
      if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
    }, 100);
  }
}

