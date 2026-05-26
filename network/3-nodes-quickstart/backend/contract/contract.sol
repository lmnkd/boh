// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title HealthDataValidator
/// @author
/// @notice Smart contract per la validazione decentralizzata di dati sanitari
/// @dev Utilizza AccessControl di OpenZeppelin per la gestione dei ruoli
contract HealthDataValidator is AccessControl, ReentrancyGuard {

    /// @notice Ruolo assegnato ai medici
    bytes32 public constant DOCTOR_ROLE    = keccak256("DOCTOR_ROLE");

    /// @notice Ruolo assegnato ai validatori
    bytes32 public constant VALIDATOR_ROLE = keccak256("VALIDATOR_ROLE");

    /// @notice Ruolo assegnato alle autorità sanitarie
    bytes32 public constant AUTHORITY_ROLE = keccak256("AUTHORITY_ROLE");
    
    /// @notice Ruolo assegnato agli oracoli
    bytes32 public constant ORACLE_ROLE    = keccak256("ORACLE_ROLE");

    /// @notice Ruolo assegnato ai pazienti
    bytes32 public constant PATIENT_ROLE   = keccak256("PATIENT_ROLE");

    /// @notice Stato di un record sanitario
    enum Status { PENDING, APPROVED, REJECTED }

    /// @notice Informazioni relative a una visita medica
    struct Visit {
        address doctor;
        address patient;
        bytes32 patientId;
        bytes32 dataHash;
        bool confirmed;
    }

    /// @notice Record sanitario sottoposto a validazione
    struct Record {
        uint256 visitId;
        address authority;
        bytes32 patientId;
        bytes32 dataHash;
        Status status;
        uint256 approveVotes;
        uint256 rejectVotes;
        mapping(address => bool) voted;
    }

    /// @notice Probabilità calcolata tramite sistema bayesiano
    struct Probability {
        uint256 recordId;
        uint256 prior;
        uint256 posterior;
        uint256 updatedAt;
    }

    address[] private validatorList;
    mapping(address => bool) private isValidatorMap;
    uint256 private validatorCount;

    /// @notice Numero totale di visite registrate
    uint256 public visitCount;

    /// @notice Numero totale di record registrati
    uint256 public recordCount;

    /// @notice Numero totale di probabilità registrate
    uint256 public probabilityCount;

    mapping(uint256 => Visit)        private visits;
    mapping(uint256 => Record)       private records;
    mapping(uint256 => Probability)  private probabilities;

    /// @notice Indica se una visita possiede già un record associato
    mapping(uint256 => bool)         public visitHasRecord;

    /// @notice Emesso quando una visita viene registrata
    /// @param visitId ID della visita
    /// @param doctor Indirizzo del medico
    /// @param patient Indirizzo del paziente
    event VisitSubmitted(uint256 visitId, address doctor, address patient);

    /// @notice Emesso quando il paziente conferma una visita
    /// @param visitId ID della visita
    /// @param patient Indirizzo del paziente
    event VisitConfirmed(uint256 visitId, address patient);

    /// @notice Emesso quando viene proposto un nuovo record
    /// @param recordId ID del record
    /// @param visitId ID della visita associata
    event RecordProposed(uint256 recordId, uint256 visitId);

    /// @notice Emesso quando un validatore vota un record
    /// @param recordId ID del record
    /// @param voter Indirizzo del validatore
    /// @param approve True se approvato, false se rifiutato
    event VoteCast(uint256 recordId, address voter, bool approve);

    /// @notice Emesso quando un record viene finalizzato
    /// @param recordId ID del record
    /// @param status Stato finale del record
    event RecordFinalized(uint256 recordId, Status status);

    /// @notice Emesso quando viene aggiornata una probabilità
    /// @param probId ID della probabilità
    /// @param recordId ID del record associato
    event ProbabilityUpdated(uint256 probId, uint256 recordId);

    /// @notice Costruttore del contratto
    /// @param initialValidators Lista iniziale dei validatori
    constructor(address[] memory initialValidators) {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);

        if (initialValidators.length == 0) {
            _addValidator(msg.sender);
            return;
        }

        for (uint i = 0; i < initialValidators.length; i++) {
            _addValidator(initialValidators[i]);
        }
    }

    /// @notice Aggiunge internamente un validatore
    /// @param a Indirizzo del validatore
    function _addValidator(address a) internal {
        if (!isValidatorMap[a]) {
            isValidatorMap[a] = true;
            validatorList.push(a);
            validatorCount++;
            _grantRole(VALIDATOR_ROLE, a);
        }
    }

    /// @notice Rimuove internamente un validatore
    /// @param a Indirizzo del validatore
    function _removeValidator(address a) internal {
        if (isValidatorMap[a]) {
            isValidatorMap[a] = false;
            validatorCount--;
            for (uint i = 0; i < validatorList.length; i++) {
                if (validatorList[i] == a) {
                    validatorList[i] = validatorList[validatorList.length - 1];
                    validatorList.pop();
                    break;
                }
            }
        }
    }

    /// @notice Assegna il ruolo di medico
    /// @param a Indirizzo del medico
    function addDoctor(address a)    external onlyRole(DEFAULT_ADMIN_ROLE) { grantRole(DOCTOR_ROLE, a); }

    /// @notice Assegna il ruolo di autorità sanitaria
    /// @param a Indirizzo dell'autorità
    function addAuthority(address a) external onlyRole(DEFAULT_ADMIN_ROLE) { grantRole(AUTHORITY_ROLE, a); }

    /// @notice Assegna il ruolo di oracolo
    /// @param a Indirizzo dell'oracolo
    function addOracle(address a)    external onlyRole(DEFAULT_ADMIN_ROLE) { grantRole(ORACLE_ROLE, a); }

    /// @notice Assegna il ruolo di paziente
    /// @param a Indirizzo del paziente
    function addPatient(address a)   external onlyRole(DEFAULT_ADMIN_ROLE) { grantRole(PATIENT_ROLE, a); }

    /// @notice Aggiunge un nuovo validatore
    /// @param a Indirizzo del validatore
    function addValidator(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _addValidator(a);
    }

    /// @notice Rimuove un validatore
    /// @param a Indirizzo del validatore
    function removeValidator(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _removeValidator(a);
        revokeRole(VALIDATOR_ROLE, a);
    }

    /// @notice Restituisce la lista dei validatori
    /// @return Lista degli indirizzi dei validatori
    function getValidators() external view returns (address[] memory) {
        return validatorList;
    }

    /// @notice Registra una nuova visita medica
    /// @dev Crea una nuova visita associata al medico chiamante
    /// @param patient Indirizzo del paziente associato alla visita
    /// @param patientId Hash identificativo del paziente
    /// @param dataHash Hash dei dati clinici della visita
    /// @return visitId Identificativo univoco della visita creata
    function submitVisit(
        address patient,
        bytes32 patientId,
        bytes32 dataHash
    ) external returns (uint256 visitId) {
        visitId = ++visitCount;
        visits[visitId] = Visit({
            doctor:    msg.sender,
            patient:   patient,
            patientId: patientId,
            dataHash:  dataHash,
            confirmed: false
        });
        emit VisitSubmitted(visitId, msg.sender, patient);
    }

    /// @notice Conferma una visita medica da parte del paziente
    /// @dev Solo il paziente associato può confermare la visita
    /// @param visitId Identificativo della visita da confermare
    function confirmVisit(uint256 visitId) external {
        require(visitId > 0 && visitId <= visitCount, "Invalid visit");
        Visit storage v = visits[visitId];
        require(msg.sender == v.patient, "Not patient");
        require(!v.confirmed, "Already confirmed");
        v.confirmed = true;
        emit VisitConfirmed(visitId, msg.sender);
    }

    /// @notice Propone un nuovo record sanitario validabile
    /// @dev Può essere chiamata solo da un'autorità autorizzata
    /// @param visitId Identificativo della visita associata
    /// @param dataHash Hash dei dati clinici da validare
    /// @return recordId Identificativo del record creato
    function proposeRecord(uint256 visitId, bytes32 dataHash)
        external
        onlyRole(AUTHORITY_ROLE)
        returns (uint256 recordId)
    {
        require(visitId > 0 && visitId <= visitCount, "Invalid visit");
        Visit storage v = visits[visitId];
        require(v.confirmed, "Visit not confirmed");
        require(!visitHasRecord[visitId], "Record exists");
        require(dataHash == v.dataHash, "Data mismatch");

        recordId = ++recordCount;
        Record storage r = records[recordId];
        r.visitId    = visitId;
        r.authority  = msg.sender;
        r.patientId  = v.patientId;
        r.dataHash   = dataHash;
        r.status     = Status.PENDING;

        visitHasRecord[visitId] = true;
        emit RecordProposed(recordId, visitId);
    }

    /// @notice Permette a un validatore di votare un record
    /// @dev Ogni validatore può votare una sola volta per record
    /// @param recordId ID del record
    /// @param approve True per approvare, false per rifiutare
    function vote(uint256 recordId, bool approve)
        external
        onlyRole(VALIDATOR_ROLE)
        nonReentrant
    {
        require(recordId > 0 && recordId <= recordCount, "Invalid record");
        Record storage r = records[recordId];
        require(!r.voted[msg.sender], "Already voted");
        require(r.status == Status.PENDING, "Finalized");

        r.voted[msg.sender] = true;

        if (approve) r.approveVotes++;
        else         r.rejectVotes++;

        emit VoteCast(recordId, msg.sender, approve);
    }

    function finalizeRecord(uint256 recordId, bool approved)
        external
        onlyRole(AUTHORITY_ROLE)
    {
        require(recordId > 0 && recordId <= recordCount, "Invalid record");
        Record storage r = records[recordId];
        require(r.status == Status.PENDING, "Already finalized");

        r.status = approved ? Status.APPROVED : Status.REJECTED;

        emit RecordFinalized(recordId, r.status);
    }

    /// @notice Aggiorna la probabilità associata a un record approvato
    /// @dev Può essere eseguita solo da un oracle autorizzato
    /// @param recordId Identificativo del record approvato
    /// @param prior Probabilità prior calcolata off-chain
    /// @param posterior Probabilità posterior aggiornata
    /// @return probId Identificativo della probabilità registrata
    function updateProbability(
        uint256 recordId,
        uint256 prior,
        uint256 posterior
    ) external onlyRole(ORACLE_ROLE) returns (uint256 probId) {
        require(recordId > 0 && recordId <= recordCount, "Invalid record");
        require(records[recordId].status == Status.APPROVED, "Not approved");

        probId = ++probabilityCount;
        probabilities[probId] = Probability(recordId, prior, posterior, block.timestamp);
        emit ProbabilityUpdated(probId, recordId);
    }

    /// @notice Restituisce i dati di una visita
    /// @param id Identificativo della visita
    /// @return Visit Struttura completa della visita
    function getVisit(uint256 id) external view returns (Visit memory) {
        require(id > 0 && id <= visitCount, "Invalid visit");
        return visits[id];
    }

    /// @notice Restituisce i dati di un record sanitario
    /// @param id Identificativo del record
    /// @return visitId Identificativo della visita associata
    /// @return authority Indirizzo dell'autorità che ha creato il record
    /// @return patientId Hash identificativo del paziente
    /// @return dataHash Hash dei dati clinici
    /// @return status Stato corrente del record
    /// @return approveVotes Numero di voti favorevoli
    /// @return rejectVotes Numero di voti contrari
    function getRecord(uint256 id)
        external
        view
        returns (
            uint256 visitId,
            address authority,
            bytes32 patientId,
            bytes32 dataHash,
            Status status,
            uint256 approveVotes,
            uint256 rejectVotes
        )
    {
        require(id > 0 && id <= recordCount, "Invalid record");
        Record storage r = records[id];
        return (r.visitId, r.authority, r.patientId, r.dataHash, r.status, r.approveVotes, r.rejectVotes);
    }

    /// @notice Verifica se un validatore ha già votato
    /// @param recordId Identificativo del record
    /// @param user Indirizzo del validatore
    /// @return True se l'utente ha già votato
    function hasVoted(uint256 recordId, address user) external view returns (bool) {
        return records[recordId].voted[user];
    }

    /// @notice Restituisce una probabilità registrata
    /// @param id Identificativo della probabilità
    /// @return Probability Struttura completa della probabilità
    function getProbability(uint256 id) external view returns (Probability memory) {
        require(id > 0 && id <= probabilityCount, "Invalid prob");
        return probabilities[id];
    }
}