import React, { useState } from 'react';

function QueueManager({ queue = [], onQueueChange, isRendering, isPaused, disabled }) {
  const [newAudioUrl, setNewAudioUrl] = useState('');
  const [newVideoUrl1, setNewVideoUrl1] = useState('');
  const [newVideoUrl2, setNewVideoUrl2] = useState('');
  const [newVideoSpeed1, setNewVideoSpeed1] = useState('1.0');
  const [newVideoSpeed2, setNewVideoSpeed2] = useState('1.0');

  const handleAddItem = () => {
    const audioInput = newAudioUrl.trim();
    const videoInput1 = newVideoUrl1.trim();
    const videoInput2 = newVideoUrl2.trim();
    const speed1 = parseFloat(newVideoSpeed1) || 1.0;
    const speed2 = parseFloat(newVideoSpeed2) || 1.0;
    
    if (!audioInput || !videoInput1 || !videoInput2) {
      alert('Vui lòng nhập đầy đủ cả 3 link (Link 1: Audio+Thumbnail, Link 2: Video 1, Link 3: Video 2)');
      return;
    }
    
    if (!audioInput.startsWith('http') || !videoInput1.startsWith('http') || !videoInput2.startsWith('http')) {
      alert('Vui lòng nhập link YouTube hợp lệ (bắt đầu bằng http)');
      return;
    }
    
    if (speed1 <= 0 || speed2 <= 0) {
      alert('Tốc độ phát phải lớn hơn 0');
      return;
    }
    
    const newItem = {
      audioUrl: audioInput,
      videoUrl1: videoInput1,
      videoUrl2: videoInput2,
      videoSpeed1: speed1,
      videoSpeed2: speed2
    };
    
    onQueueChange([...queue, newItem]);
    setNewAudioUrl('');
    setNewVideoUrl1('');
    setNewVideoUrl2('');
    setNewVideoSpeed1('1.0');
    setNewVideoSpeed2('1.0');
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
          <label>Link 2 (Video 1):</label>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <input
              type="text"
              className="queue-input-single"
              placeholder="Nhập link YouTube để tải Video 1..."
              value={newVideoUrl1}
              onChange={(e) => setNewVideoUrl1(e.target.value)}
              disabled={disabled}
              style={{ flex: 1 }}
            />
            <label style={{ whiteSpace: 'nowrap', fontSize: '12px' }}>Tốc độ:</label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="10"
              value={newVideoSpeed1}
              onChange={(e) => setNewVideoSpeed1(e.target.value)}
              disabled={disabled}
              style={{ width: '60px', padding: '5px' }}
              placeholder="1.0"
            />
          </div>
        </div>
        <div className="queue-input-group">
          <label>Link 3 (Video 2):</label>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <input
              type="text"
              className="queue-input-single"
              placeholder="Nhập link YouTube để tải Video 2..."
              value={newVideoUrl2}
              onChange={(e) => setNewVideoUrl2(e.target.value)}
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
              value={newVideoSpeed2}
              onChange={(e) => setNewVideoSpeed2(e.target.value)}
              disabled={disabled}
              style={{ width: '60px', padding: '5px' }}
              placeholder="1.0"
            />
          </div>
        </div>
        <button 
          className="queue-add-btn"
          onClick={handleAddItem}
          disabled={disabled || !newAudioUrl.trim() || !newVideoUrl1.trim() || !newVideoUrl2.trim() || !newVideoSpeed1 || !newVideoSpeed2}
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
                  <strong>Link 1:</strong> {item.audioUrl.length > 35 ? `${item.audioUrl.substring(0, 35)}...` : item.audioUrl}
                </div>
                <div className="queue-item-url" title={item.videoUrl1}>
                  <strong>Link 2:</strong> {item.videoUrl1.length > 35 ? `${item.videoUrl1.substring(0, 35)}...` : item.videoUrl1}
                  {item.videoSpeed1 && item.videoSpeed1 !== 1.0 && <span style={{ marginLeft: '10px', color: '#00ff88' }}>(x{item.videoSpeed1})</span>}
                </div>
                <div className="queue-item-url" title={item.videoUrl2}>
                  <strong>Link 3:</strong> {item.videoUrl2.length > 35 ? `${item.videoUrl2.substring(0, 35)}...` : item.videoUrl2}
                  {item.videoSpeed2 && item.videoSpeed2 !== 1.0 && <span style={{ marginLeft: '10px', color: '#00ff88' }}>(x{item.videoSpeed2})</span>}
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

