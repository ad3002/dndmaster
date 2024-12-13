class BaseAgent {
    constructor(name, role) {
        this.name = name;
        this.role = role;
        this.memory = [];
        this.currentState = 'idle';
    }

    // Base message handling
    async processMessage(message, sender) {
        this.memory.push({ sender, message, timestamp: Date.now() });
        return this.generateResponse(message, sender);
    }

    // Response generation based on role
    async generateResponse(message, sender) {
        throw new Error('Method must be implemented by child classes');
    }

    // Memory management
    getRecentMemories(limit = 5) {
        return this.memory.slice(-limit);
    }
}

class DungeonMaster extends BaseAgent {
    constructor() {
        super('DM', 'gamemaster');
        this.currentScene = null;
        this.gameState = {
            players: [],
            currentLocation: 'starting_point',
            activeQuests: [],
            npcs: []
        };
    }

    async generateResponse(message, sender) {
        // DM specific logic for managing game flow and responding to players
        if (message.includes('attack')) {
            return this.handleCombat(sender, message);
        } else if (message.includes('investigate')) {
            return this.handleInvestigation(sender, message);
        }
        
        // Default narrative response
        return {
            type: 'narration',
            content: `The DM acknowledges ${sender}'s action and describes the scene...`
        };
    }

    handleCombat(player, action) {
        return {
            type: 'combat',
            content: `Rolling dice for ${player}'s combat action...`
        };
    }

    handleInvestigation(player, action) {
        return {
            type: 'investigation',
            content: `${player} investigates the area...`
        };
    }
}

class PlayerCharacter extends BaseAgent {
    constructor(name, characterClass) {
        super(name, 'player');
        this.characterClass = characterClass;
        this.stats = {
            hp: 100,
            mana: 100,
            inventory: []
        };
    }

    async generateResponse(message, sender) {
        // Player character specific logic
        if (sender === 'DM') {
            return this.respondToDM(message);
        }
        return this.respondToPlayer(message, sender);
    }

    respondToDM(message) {
        // Generate response based on character class and personality
        return {
            type: 'action',
            content: `${this.name} the ${this.characterClass} responds to the situation...`
        };
    }

    respondToPlayer(message, sender) {
        return {
            type: 'interaction',
            content: `${this.name} interacts with ${sender}...`
        };
    }
}

class GameCoordinator {
    constructor() {
        this.dm = new DungeonMaster();
        this.players = [];
        this.messageQueue = [];
    }

    addPlayer(name, characterClass) {
        const player = new PlayerCharacter(name, characterClass);
        this.players.push(player);
        return player;
    }

    async processGameTurn() {
        while (this.messageQueue.length > 0) {
            const { sender, recipient, message } = this.messageQueue.shift();
            const response = await recipient.processMessage(message, sender.name);
            
            // Broadcast response to all agents
            await this.broadcastResponse(sender, recipient, response);
        }
    }

    async broadcastResponse(sender, recipient, response) {
        // Send response to all agents except the sender
        const targets = [this.dm, ...this.players].filter(
            agent => agent !== sender
        );

        for (const target of targets) {
            await target.processMessage(response, recipient.name);
        }
    }

    // Example game initialization
    async initializeGame() {
        // Add players
        this.addPlayer('Warrior1', 'Fighter');
        this.addPlayer('Mage1', 'Wizard');
        this.addPlayer('Rogue1', 'Rogue');
        this.addPlayer('Cleric1', 'Cleric');

        // Start game with DM introduction
        this.messageQueue.push({
            sender: this.dm,
            recipient: this.players[0],
            message: 'Welcome to the adventure! You find yourselves in a dimly lit tavern...'
        });

        // Process first game turn
        await this.processGameTurn();
    }
}

// Example usage
const game = new GameCoordinator();
game.initializeGame();