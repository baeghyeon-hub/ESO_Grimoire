<script>
  import MessageBubble from "./MessageBubble.svelte";

  let { messages = [], loading = false } = $props();
  let listEl;

  // Scroll to bottom when new messages added
  $effect(() => {
    messages.length; // dependency
    if (listEl) {
      requestAnimationFrame(() => {
        listEl.scrollTop = listEl.scrollHeight;
      });
    }
  });
</script>

<div class="list" bind:this={listEl}>
  {#each messages as msg, i (i)}
    <MessageBubble role={msg.role} content={msg.content} />
  {/each}
  {#if loading}
    <div class="typing">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    </div>
  {/if}
</div>

<style>
  .list {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .list::-webkit-scrollbar {
    width: 4px;
  }
  .list::-webkit-scrollbar-thumb {
    background: rgba(200, 168, 78, 0.2);
    border-radius: 2px;
  }
  .typing {
    display: flex;
    gap: 4px;
    padding: 12px 16px;
    align-self: flex-start;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #9a8a68;
    animation: bounce 1.2s infinite;
  }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-6px); }
  }
</style>
