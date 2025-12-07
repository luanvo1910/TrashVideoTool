import React, { useState } from 'react';

function QueueManager({ queue = [], onQueueChange, isRendering, isPaused, disabled }) {
  const [newAudioUrl, setNewAudioUrl] = useState('');
  const [newVideoUrl, setNewVideoUrl] = useState('');
  const [newVideoSpeed, setNewVideoSpeed] = useState('1.0');

  const handleAddItem = () => {
    const audioInput = newAudioUrl.trim();
    const videoInput = newVideoUrl.trim();
    const speed = parseFloat(newVideoSpeed) || 1.0;
    
    if (!audioInput || !videoInput) {
      alert('Vui lòng nhập đầy đủ cả 2 link (Link 1: Audio+Thumbnail, Link 2: Video)');
      return;
    }
    
    if (!audioInput.startsWith('http') || !videoInput.startsWith('http')) {
      alert('Vui lòng nhập link YouTube hợp lệ (bắt đầu bằng http)');
      return;
    }
    
    if (speed <= 0) {
      alert('Tốc độ phát phải lớn hơn 0');
      return;
    }
    
    const newItem = {
      audioUrl: audioInput,
      videoUrl: videoInput,
      videoSpeed: speed
    };
    
    onQueueChange([...queue, newItem]);
    setNewAudioUrl('');
    setNewVideoUrl('');
    setNewVideoSpeed('1.0');
  };

  const handleRemoveItem = (index) => {
    onQueueChange(queue.filter((_, i) => i !== index));
  };

  const handleMoveUp = (index) => {
    if (index === 0) return;
    const newQueue = [...queue];
    [newQueue[index - 1], newQueue[index]] = [newQueue[index], newQueue[index - 1]];
    onQueueChange(newQueue);
  };

  const handleMoveDown = (index) => {
    if (index === queue.length - 1) return;
    const newQueue = [...queue];
    [newQueue[index], newQueue[index + 1]] = [newQueue[index + 1], newQueue[index]];
    onQueueChange(newQueue);
  };

  const handleClearAll = () => {
    if (window.confirm('Bạn có chắc muốn xóa tất cả items trong hàng chờ?')) {
      onQueueChange([]);
    }
  };

  return (
    <div className="queue-manager">
      <div className="queue-manager-header">
        <h3>Quản lý Hàng chờ ({queue.length})</h3>
        {queue.length > 0 && (
          <button 
            className="clear-all-btn" 
            onClick={handleClearAll}
            disabled={disabled || (isRendering && !isPaused)}
            title="Xóa tất cả"
          >
            🗑️ Xóa hết
          </button>
        )}
      </div>

      <div className="queue-add-section">
        <div className="queue-input-group">
          <label>Link 1 (Audio + Thumbnail):</label>
          <input
            type="text"
            className="queue-input-single"
            placeholder="Nhập link YouTube để tải Audio + Thumbnail..."
            value={newAudioUrl}
            onChange={(e) => setNewAudioUrl(e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="queue-input-group">
          <label>Link 2 (Video):</label>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <input
              type="text"
              className="queue-input-single"
              placeholder="Nhập link YouTube để tải Video..."
              value={newVideoUrl}
              onChange={(e) => setNewVideoUrl(e.target.value)}
              disabled={disabled}
              style={{ flex: 1 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAddItem();
                }
              }}
            />
            <label style={{ whiteSpace: 'nowrap', fontSize: '12px' }}>Tốc độ:</label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="10"
              value={newVideoSpeed}
              onChange={(e) => setNewVideoSpeed(e.target.value)}
              disabled={disabled}
              style={{ width: '60px', padding: '5px' }}
              placeholder="1.0"
            />
          </div>
        </div>
        <button 
          className="queue-add-btn"
          onClick={handleAddItem}
          disabled={disabled || !newAudioUrl.trim() || !newVideoUrl.trim() || !newVideoSpeed}
        >
          ➕ Thêm
        </button>
      </div>

      <div className="queue-list">
        {queue.length === 0 ? (
          <div className="queue-empty">Chưa có item nào trong hàng chờ</div>
        ) : (
          queue.map((item, index) => (
            <div key={index} className="queue-item">
              <div className="queue-item-number">{index + 1}</div>
              <div className="queue-item-urls">
                <div className="queue-item-url" title={item.audioUrl}>
                  <strong>Link 1:</strong> {item.audioUrl.length > 50 ? `${item.audioUrl.substring(0, 50)}...` : item.audioUrl}
                </div>
                <div className="queue-item-url" title={item.videoUrl}>
                  <strong>Link 2:</strong> {item.videoUrl.length > 50 ? `${item.videoUrl.substring(0, 50)}...` : item.videoUrl}
                  {item.videoSpeed && item.videoSpeed !== 1.0 && <span style={{ marginLeft: '10px', color: '#00ff88' }}>(x{item.videoSpeed})</span>}
                </div>
              </div>
              <div className="queue-item-actions">
                <button
                  className="queue-action-btn"
                  onClick={() => handleMoveUp(index)}
                  disabled={disabled || (isRendering && !isPaused) || index === 0}
                  title="Lên trên"
                >
                  ⬆️
                </button>
                <button
                  className="queue-action-btn"
                  onClick={() => handleMoveDown(index)}
                  disabled={disabled || (isRendering && !isPaused) || index === queue.length - 1}
                  title="Xuống dưới"
                >
                  ⬇️
                </button>
                <button
                  className="queue-action-btn queue-delete-btn"
                  onClick={() => handleRemoveItem(index)}
                  disabled={disabled || (isRendering && !isPaused)}
                  title="Xóa"
                >
                  ❌
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default QueueManager;

