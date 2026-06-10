/* nh-wallet.js — Narrow Highway frontend wallet helper.
 *
 * Self-custodial only. We never see keys. The library:
 *   - Detects window.ethereum (EIP-1193)
 *   - Asks user to connect their wallet
 *   - Helps switch to Base / Optimism / Ethereum
 *   - Composes a USDC transfer (ERC20) or native ETH transfer
 *   - On send confirmation, posts the txid to /wallet/record-tip for the
 *     transparency ledger
 *
 * Patron Circle is user-scheduled (Phase 1). We provide an .ics calendar
 * reminder that the patron drops into their own calendar.
 *
 * Usage:
 *   const operator = await NHWallet.fetchOperator();
 *   const acct = await NHWallet.connect();
 *   const result = await NHWallet.sendUSDC({
 *     to: operator.evm_address,
 *     amount_usd: 10,
 *     chain: 'base',
 *     intent: 'patron',
 *     message: 'first month of patron circle',
 *   });
 */
(function (global) {
  const CHAINS = {
    base: {
      chainId: '0x2105', // 8453
      chainName: 'Base',
      rpcUrls: ['https://mainnet.base.org'],
      nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
      blockExplorerUrls: ['https://basescan.org'],
      usdc_contract: '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', // Base USDC
    },
    optimism: {
      chainId: '0xa', // 10
      chainName: 'Optimism',
      rpcUrls: ['https://mainnet.optimism.io'],
      nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
      blockExplorerUrls: ['https://optimistic.etherscan.io'],
      usdc_contract: '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85', // Optimism USDC
    },
    ethereum: {
      chainId: '0x1', // 1
      chainName: 'Ethereum',
      rpcUrls: ['https://eth.llamarpc.com'],
      nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
      blockExplorerUrls: ['https://etherscan.io'],
      usdc_contract: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', // Ethereum mainnet USDC
    },
  };

  const HAS_WALLET = typeof window !== 'undefined' && !!window.ethereum;

  async function fetchOperator() {
    try {
      const r = await fetch('/wallet/operator-address', { cache: 'no-store' });
      if (!r.ok) return null;
      return await r.json();
    } catch (_) { return null; }
  }

  async function connect() {
    if (!HAS_WALLET) throw new Error('No browser wallet detected. Install Coinbase Wallet, MetaMask, Rainbow, etc.');
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    if (!accounts || accounts.length === 0) throw new Error('No account selected.');
    const chainId = await window.ethereum.request({ method: 'eth_chainId' });
    return { address: accounts[0], chainId: chainId };
  }

  async function ensureChain(chainKey) {
    if (!HAS_WALLET) throw new Error('No wallet');
    const target = CHAINS[chainKey];
    if (!target) throw new Error('Unknown chain: ' + chainKey);
    const current = await window.ethereum.request({ method: 'eth_chainId' });
    if (current.toLowerCase() === target.chainId.toLowerCase()) return current;
    // Try switch first
    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: target.chainId }],
      });
      return target.chainId;
    } catch (e) {
      // 4902: chain not added. Try to add it.
      if (e && (e.code === 4902 || (e.data && e.data.originalError && e.data.originalError.code === 4902))) {
        await window.ethereum.request({
          method: 'wallet_addEthereumChain',
          params: [{
            chainId: target.chainId,
            chainName: target.chainName,
            rpcUrls: target.rpcUrls,
            nativeCurrency: target.nativeCurrency,
            blockExplorerUrls: target.blockExplorerUrls,
          }],
        });
        return target.chainId;
      }
      throw e;
    }
  }

  function toUSDCBaseUnits(amount_usd) {
    // USDC has 6 decimals across all chains.
    // amount_usd → integer micro-USDC, then hex.
    const micro = BigInt(Math.round(amount_usd * 1_000_000));
    return '0x' + micro.toString(16);
  }

  function buildERC20TransferData(toAddress, amount_usd) {
    // function transfer(address to, uint256 amount) — ERC20
    // selector: 0xa9059cbb
    const selector = 'a9059cbb';
    const toPadded = toAddress.replace(/^0x/, '').toLowerCase().padStart(64, '0');
    const micro = BigInt(Math.round(amount_usd * 1_000_000));
    const amtPadded = micro.toString(16).padStart(64, '0');
    return '0x' + selector + toPadded + amtPadded;
  }

  async function sendUSDC(opts) {
    if (!HAS_WALLET) throw new Error('No wallet');
    if (!opts || !opts.to || !opts.amount_usd) throw new Error('to + amount_usd required');
    const chainKey = opts.chain || 'base';
    const chain = CHAINS[chainKey];
    if (!chain) throw new Error('Unsupported chain ' + chainKey);

    const { address } = await connect();
    await ensureChain(chainKey);
    const txParams = {
      from: address,
      to: chain.usdc_contract,
      data: buildERC20TransferData(opts.to, opts.amount_usd),
      value: '0x0',
    };
    const txid = await window.ethereum.request({
      method: 'eth_sendTransaction',
      params: [txParams],
    });
    // Record for transparency
    try {
      await fetch('/wallet/record-tip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          txid: txid,
          chain: chainKey,
          amount_usd: opts.amount_usd,
          token: 'USDC',
          from_redacted: address.slice(0, 6) + '…' + address.slice(-4),
          intent: opts.intent || 'patron',
          creator_id: opts.creator_id || null,
          message: (opts.message || '').slice(0, 200),
        }),
      });
    } catch (e) {
      console.warn('record-tip failed (tx still on-chain):', e);
    }
    return { txid: txid, chain: chainKey, explorer: chain.blockExplorerUrls[0] + '/tx/' + txid };
  }

  async function sendETH(opts) {
    if (!HAS_WALLET) throw new Error('No wallet');
    const chainKey = opts.chain || 'base';
    const chain = CHAINS[chainKey];
    const { address } = await connect();
    await ensureChain(chainKey);
    // Convert USD → ETH? We don't have a price oracle in Phase 1. Caller passes amount_eth directly.
    if (!opts.amount_eth) throw new Error('amount_eth required for sendETH (no price oracle in Phase 1)');
    const wei = BigInt(Math.round(opts.amount_eth * 1e18));
    const txParams = {
      from: address,
      to: opts.to,
      value: '0x' + wei.toString(16),
    };
    const txid = await window.ethereum.request({
      method: 'eth_sendTransaction',
      params: [txParams],
    });
    try {
      await fetch('/wallet/record-tip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          txid: txid,
          chain: chainKey,
          amount_usd: null, // unknown without a price oracle
          token: 'ETH',
          from_redacted: address.slice(0, 6) + '…' + address.slice(-4),
          intent: opts.intent || 'patron',
          creator_id: opts.creator_id || null,
          message: (opts.message || '').slice(0, 200),
        }),
      });
    } catch (_) {}
    return { txid: txid, chain: chainKey, explorer: chain.blockExplorerUrls[0] + '/tx/' + txid };
  }

  function makePatronCalendarReminder(opts) {
    // Returns an .ics file body for the patron to drop into their calendar.
    // opts: amount_usd, cadence ('monthly' | 'quarterly' | 'annually'), operator_address
    const cadence = opts.cadence || 'monthly';
    const rrule = {
      monthly: 'FREQ=MONTHLY',
      quarterly: 'FREQ=MONTHLY;INTERVAL=3',
      annually: 'FREQ=YEARLY',
    }[cadence] || 'FREQ=MONTHLY';
    const now = new Date();
    const start = new Date(now.getTime() + 24 * 60 * 60 * 1000); // tomorrow
    const fmt = function (d) {
      return d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    };
    const uid = 'nh-patron-' + now.getTime() + '@narrowhighway.com';
    const summary = 'Narrow Highway · Patron Circle ($' + (opts.amount_usd || 25) + ')';
    const desc = 'Send $' + (opts.amount_usd || 25) + ' USDC on Base to: ' +
      (opts.operator_address || '<operator address>') +
      '. Open your wallet (Coinbase Wallet, MetaMask, etc.) and send. ' +
      'This is patron support for narrowhighway.com — never auto-charged.';
    return [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Narrow Highway//Patron Reminder//EN',
      'BEGIN:VEVENT',
      'UID:' + uid,
      'DTSTAMP:' + fmt(now),
      'DTSTART:' + fmt(start),
      'DURATION:PT15M',
      'SUMMARY:' + summary,
      'DESCRIPTION:' + desc.replace(/\n/g, '\\n'),
      'RRULE:' + rrule,
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n');
  }

  function downloadICS(filename, body) {
    const blob = new Blob([body], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  global.NHWallet = {
    HAS_WALLET: HAS_WALLET,
    CHAINS: CHAINS,
    fetchOperator: fetchOperator,
    connect: connect,
    ensureChain: ensureChain,
    sendUSDC: sendUSDC,
    sendETH: sendETH,
    makePatronCalendarReminder: makePatronCalendarReminder,
    downloadICS: downloadICS,
  };
})(typeof window !== 'undefined' ? window : this);
