import pkg from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import { EventEmitter } from 'events';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const { Client, LocalAuth } = pkg;
const __dirname = dirname(fileURLToPath(import.meta.url));

// Reconnection config
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 5000; // 5s, 10s, 20s, 40s, 80s

class WhatsAppClient extends EventEmitter {
  constructor() {
    super();
    this.client = null;
    this.isReady = false;
    this.messageCallback = null;
    this._reconnectAttempts = 0;
    this._reconnecting = false;
    this._autoReconnect = true;
  }

  initialize() {
    this.client = new Client({
      authStrategy: new LocalAuth({
        dataPath: join(__dirname, '../../.wwebjs_auth'),
      }),
      puppeteer: {
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      },
    });

    this.client.on('qr', (qr) => {
      qrcode.generate(qr, { small: true });
      this.emit('qr', qr);
    });

    this.client.on('ready', async () => {
      this.isReady = true;
      this._reconnectAttempts = 0;
      this._reconnecting = false;
      const info = this.client.info;
      const number = info?.wid?.user ?? 'desconhecido';
      console.log(`WhatsApp conectado! Numero: +${number}`);
      this.emit('ready', info);
    });

    this.client.on('message', (msg) => {
      this.emit('message', msg);
      if (typeof this.messageCallback === 'function') {
        this.messageCallback(msg);
      }
    });

    // Capture outgoing messages (user's own responses) for learning
    this.client.on('message_create', (msg) => {
      if (msg.fromMe) {
        this.emit('message_create', msg);
        if (typeof this.messageCallback === 'function') {
          this.messageCallback(msg);
        }
      }
    });

    this.client.on('disconnected', (reason) => {
      this.isReady = false;
      console.log('WhatsApp desconectado:', reason);
      this.emit('disconnected', reason);

      if (this._autoReconnect) {
        this._scheduleReconnect();
      }
    });

    this.client.initialize();
  }

  /**
   * Attempt to reconnect with exponential backoff.
   * @private
   */
  _scheduleReconnect() {
    if (this._reconnecting) return;
    if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.log(`[Reconexao] Maximo de ${MAX_RECONNECT_ATTEMPTS} tentativas atingido. Reinicie o app manualmente.`);
      this.emit('reconnect_failed');
      return;
    }

    this._reconnecting = true;
    this._reconnectAttempts++;
    const delay = RECONNECT_BASE_DELAY_MS * Math.pow(2, this._reconnectAttempts - 1);

    console.log(`[Reconexao] Tentativa ${this._reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS} em ${delay / 1000}s...`);

    setTimeout(async () => {
      try {
        // Destroy old client cleanly
        if (this.client) {
          try { await this.client.destroy(); } catch { /* ignore */ }
        }
        this._reconnecting = false;
        this.initialize();
      } catch (err) {
        console.error('[Reconexao] Erro:', err.message);
        this._reconnecting = false;
        this._scheduleReconnect();
      }
    }, delay);
  }

  /**
   * Set an external callback to be invoked on every incoming message.
   * @param {Function} fn - Callback receiving the raw whatsapp-web.js Message object.
   */
  onMessage(fn) {
    this.messageCallback = fn;
  }

  /**
   * Send a text message to a chat.
   * @param {string} chatId - The WhatsApp chat ID (e.g. "5511999999999@c.us").
   * @param {string} text - The message body to send.
   * @returns {Promise<Message>}
   */
  async sendMessage(chatId, text) {
    if (!this.isReady) {
      throw new Error('WhatsApp client is not ready yet.');
    }
    return this.client.sendMessage(chatId, text);
  }

  /**
   * Return a list of recent chats.
   * @returns {Promise<Chat[]>}
   */
  async getChats() {
    if (!this.isReady) {
      throw new Error('WhatsApp client is not ready yet.');
    }
    return this.client.getChats();
  }

  /**
   * Fetch message history from a specific chat.
   * @param {string} chatId - The WhatsApp chat ID.
   * @param {number} limit  - Maximum number of messages to retrieve (default 50).
   * @returns {Promise<Message[]>}
   */
  async getChatMessages(chatId, limit = 50) {
    if (!this.isReady) {
      throw new Error('WhatsApp client is not ready yet.');
    }
    const chat = await this.client.getChatById(chatId);
    return chat.fetchMessages({ limit });
  }

  /**
   * Disable auto-reconnect (e.g. during graceful shutdown).
   */
  disableAutoReconnect() {
    this._autoReconnect = false;
  }
}

// Singleton instance
const whatsappClient = new WhatsAppClient();

export { whatsappClient };
export const initialize = () => whatsappClient.initialize();
