/* Feedback adapter contract. The current implementation intentionally stays in this browser. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.BriefingFeedback = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const STORAGE_KEY = 'technical-briefing-feedback-v1';

  class FeedbackStore {
    listEvents() { throw new Error('FeedbackStore.listEvents must be implemented'); }
    current() { throw new Error('FeedbackStore.current must be implemented'); }
    toggle() { throw new Error('FeedbackStore.toggle must be implemented'); }
    exportData() { throw new Error('FeedbackStore.exportData must be implemented'); }
    clear() { throw new Error('FeedbackStore.clear must be implemented'); }
  }

  class LocalFeedbackStore extends FeedbackStore {
    constructor(storage, options = {}) {
      super();
      this.storage = storage;
      this.storageKey = options.storageKey || STORAGE_KEY;
      this.actorId = options.actorId || 'local_demo';
      this.now = options.now || (() => new Date().toISOString());
      this.makeId = options.makeId || (() => `feedback_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`);
    }

    listEvents() {
      try {
        const parsed = JSON.parse(this.storage?.getItem(this.storageKey) || '[]');
        return Array.isArray(parsed) ? parsed : [];
      } catch (_) {
        return [];
      }
    }

    _write(events) {
      this.storage?.setItem(this.storageKey, JSON.stringify(events));
      return events;
    }

    current(targetType, targetId) {
      const rows = this.listEvents().filter(row => row.target_type === targetType && row.target_id === targetId);
      const latest = rows.at(-1);
      return latest?.action === 'set' ? latest.reaction : null;
    }

    toggle(targetType, targetId, reaction) {
      if (!targetType || !targetId || !reaction) throw new Error('targetType, targetId and reaction are required');
      const action = this.current(targetType, targetId) === reaction ? 'clear' : 'set';
      const event = {
        event_id: this.makeId(),
        actor_id: this.actorId,
        target_type: targetType,
        target_id: targetId,
        reaction,
        action,
        created_at: this.now(),
        schema_version: 1,
      };
      this._write([...this.listEvents(), event]);
      return {event, current: action === 'set' ? reaction : null};
    }

    exportData() {
      return {
        schema_version: 1,
        mode: 'local_browser_demo',
        exported_at: this.now(),
        events: this.listEvents(),
      };
    }

    clear() { this.storage?.removeItem(this.storageKey); }
  }

  return {FeedbackStore, LocalFeedbackStore, STORAGE_KEY};
});
